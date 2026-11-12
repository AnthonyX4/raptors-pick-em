"""
    Pulls one season of the followed team's games from nba.com into Backend/nba_data.json,
    which seed.py then loads into the database.

    usage (from Backend/):
        uv run python harvest_scripts/harvest.py
        uv run python harvest_scripts/harvest.py --season 2025-26
        uv run python harvest_scripts/harvest.py --no-box-scores

    RUN THIS ON A NORMAL MACHINE, not in the cloud. stats.nba.com silently drops connections
    from AWS, GCP and Azure addresses, so this script works on a laptop and times out on a
    server. That is the whole reason the api never calls nba_api itself: NBA data gets in
    through this script and (later) the live feeds on cdn.nba.com, which aren't blocked.

    The file it writes maps one-to-one onto the models, so seed.py does no translating.
"""
import argparse
import json
import sys
import time
from datetime import datetime, UTC
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR)) # so config is importable regardless of cwd

from nba_api.stats.endpoints.boxscoretraditionalv3 import BoxScoreTraditionalV3
from nba_api.stats.endpoints.commonteamroster import CommonTeamRoster
from nba_api.stats.endpoints.scheduleleaguev2 import ScheduleLeagueV2
from nba_api.stats.library.parameters import Season
from nba_api.stats.static import players as static_players
from nba_api.stats.static import teams as static_teams
from requests.exceptions import RequestException

from config import settings

OUTPUT_PATH = BACKEND_DIR / "nba_data.json"

THROTTLE_SECONDS = 0.6 # stats.nba.com rate limits bursts, one request a second is safe
MAX_ATTEMPTS = 3

# the third digit of a game id is the season type. preseason (1) and the all-star
# weekend (3) aren't real games to predict, so they're left out
WANTED_GAME_TYPES = {"2", "4", "5"} # regular season, playoffs, play-in

# the nba's integer status, translated here so nothing past this script has to know it
NBA_STATUS = {1: "scheduled", 2: "live", 3: "final"}


def rows(data_set) -> list[dict]:
    """nba_api returns {"headers": [...], "data": [[...], ...]}, zip it into dicts."""
    payload = data_set.get_dict()
    return [dict(zip(payload["headers"], row)) for row in payload["data"]]


def fetch(label: str, build):
    """Call an endpoint, retrying timeouts. Returns None once it has given up."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return build()
        except RequestException as err:
            if attempt == MAX_ATTEMPTS:
                print(f"  {label}: giving up after {MAX_ATTEMPTS} attempts ({type(err).__name__}) ❌")
                return None
            wait = attempt * 2
            print(f"  {label}: {type(err).__name__}, retrying in {wait}s")
            time.sleep(wait)
    return None


def game_status(raw_status, status_text: str) -> str:
    text = (status_text or "").lower()
    if "ppd" in text or "postpone" in text:
        return "postponed"
    return NBA_STATUS.get(raw_status, "scheduled")


def to_utc_iso(value: str | None) -> str | None:
    # the api sends "2026-10-22T23:30:00Z", json has no datetime type so it stays a string
    # and seed.py parses it. normalized here so fromisoformat accepts it
    if not value:
        return None
    return value.replace("Z", "+00:00")


def to_minutes(value: str | None) -> str | None:
    """Box scores send either "32:14" or an iso duration like "PT32M14.00S". Normalize to mm:ss."""
    if not value:
        return None
    if not value.startswith("PT"):
        return value
    body = value[2:]
    minutes, _, seconds = body.partition("M")
    seconds = seconds.rstrip("S").split(".")[0] or "0"
    return f"{int(minutes or 0)}:{int(seconds):02d}"


def harvest_teams() -> list[dict]:
    """All 30 teams, from the dataset shipped inside nba_api. No request, nothing to throttle."""
    return [
        {
            "team_id": team["id"],
            "tricode": team["abbreviation"],
            "city": team["city"],
            "nickname": team["nickname"],
            "full_name": team["full_name"],
        }
        for team in static_teams.get_teams()
    ]


def harvest_games(season: str, tricode: str) -> list[dict]:
    """One request for the league's whole season, filtered down to the followed team."""
    schedule = fetch("schedule", lambda: ScheduleLeagueV2(season=season))
    if schedule is None:
        return []

    games = []
    for row in rows(schedule.season_games):
        game_id = row["gameId"]
        if game_id[2:3] not in WANTED_GAME_TYPES:
            continue
        if tricode not in (row["homeTeam_teamTricode"], row["awayTeam_teamTricode"]):
            continue

        games.append({
            "game_id": game_id,
            "season": row["seasonYear"],
            "tipoff_utc": to_utc_iso(row["gameDateTimeUTC"]),
            "status": game_status(row["gameStatus"], row["gameStatusText"]),
            "status_text": (row["gameStatusText"] or "").strip(),
            "home_team_id": row["homeTeam_teamId"],
            "away_team_id": row["awayTeam_teamId"],
            "home_score": row["homeTeam_score"] or None, # the api sends 0 for a game that hasn't happened
            "away_score": row["awayTeam_score"] or None,
            "arena_name": row["arenaName"],
        })

    games.sort(key=lambda game: game["tipoff_utc"] or "")
    return games


def harvest_players(team_ids: list[int], season: str) -> list[dict]:
    """One request per team. Names come from nba_api's offline dataset where it has them."""
    known_names = {p["id"]: (p["first_name"], p["last_name"]) for p in static_players.get_players()}
    players = []

    for index, team_id in enumerate(team_ids, start=1):
        print(f"  roster {index}/{len(team_ids)} (team {team_id})")
        roster = fetch(f"roster {team_id}", lambda: CommonTeamRoster(team_id=team_id, season=season))
        time.sleep(THROTTLE_SECONDS)
        if roster is None:
            continue

        for row in rows(roster.common_team_roster):
            player_id = row["PLAYER_ID"]
            full_name = row["PLAYER"]
            first, last = known_names.get(player_id, ("", ""))
            if not first:
                # a rookie or a signing the shipped dataset predates
                first, _, last = full_name.partition(" ")
            players.append({
                "player_id": player_id,
                "full_name": full_name,
                "first_name": first,
                "last_name": last or full_name,
                "team_id": team_id,
                "jersey_number": str(row["NUM"]) if row["NUM"] not in (None, "") else None,
                "position": row["POSITION"] or None,
            })

    return players


def harvest_box_scores(games: list[dict]) -> list[dict]:
    """One request per finished game. These are what scoring reads to find each category's leader."""
    finished = [game for game in games if game["status"] == "final"]
    stats = []

    for index, game in enumerate(finished, start=1):
        game_id = game["game_id"]
        print(f"  box score {index}/{len(finished)} ({game_id})")
        box = fetch(f"box score {game_id}", lambda: BoxScoreTraditionalV3(game_id=game_id))
        time.sleep(THROTTLE_SECONDS)
        if box is None:
            continue

        for row in rows(box.player_stats):
            stats.append({
                "game_id": row["gameId"],
                "player_id": row["personId"],
                "team_id": row["teamId"],
                # a player who didn't appear still gets a row, with the reason in comment
                "first_name": row["firstName"],
                "last_name": row["familyName"],
                "minutes": to_minutes(row["minutes"]),
                "comment": (row["comment"] or "").strip() or None,
                "points": row["points"] or 0,
                "rebounds_offensive": row["reboundsOffensive"] or 0,
                "rebounds_defensive": row["reboundsDefensive"] or 0,
                "rebounds_total": row["reboundsTotal"] or 0,
                "assists": row["assists"] or 0,
                "steals": row["steals"] or 0,
                "blocks": row["blocks"] or 0,
                "turnovers": row["turnovers"] or 0,
                "three_pointers_made": row["threePointersMade"] or 0,
            })

    return stats


def main(season: str, tricode: str, with_box_scores: bool) -> int:
    print(f"Harvesting {tricode} {season}\n")

    print("teams (offline)")
    teams = harvest_teams()
    print(f"  {len(teams)} teams\n")

    print("schedule")
    games = harvest_games(season, tricode)
    if not games:
        print("  no games, leaving the existing file alone ❌")
        return 1
    finals = sum(1 for game in games if game["status"] == "final")
    print(f"  {len(games)} games, {finals} already played\n")

    # only the teams actually on the schedule, so a partial season doesn't fetch 30 rosters
    team_ids = sorted({game["home_team_id"] for game in games} | {game["away_team_id"] for game in games})
    print(f"rosters ({len(team_ids)} teams)")
    players = harvest_players(team_ids, season)
    print(f"  {len(players)} players\n")

    player_game_stats = []
    if with_box_scores and finals:
        print(f"box scores ({finals} finished games)")
        player_game_stats = harvest_box_scores(games)
        print(f"  {len(player_game_stats)} stat lines\n")

    payload = {
        "harvested_at": datetime.now(UTC).isoformat(),
        "season": season,
        "team_tricode": tricode,
        "teams": teams,
        "games": games,
        "players": players,
        "player_game_stats": player_game_stats,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.name} ✅")
    print("Next: uv run python harvest_scripts/seed.py")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harvest a season of games from nba.com.")
    parser.add_argument("--season", default=Season.default, help=f"e.g. 2025-26 (default: {Season.default})")
    parser.add_argument("--team", default=settings.team_tricode, help="team tricode (default: from .env)")
    parser.add_argument("--no-box-scores", action="store_true", help="skip the per-game box score requests")
    args = parser.parse_args()

    sys.exit(main(args.season, args.team.upper(), with_box_scores=not args.no_box_scores))
