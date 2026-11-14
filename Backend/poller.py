"""
    The background worker that keeps the database in step with real games, so the app runs
    itself: no admin scoring games by hand, no laptop re-harvesting.

    usage (from Backend/, in its own terminal next to the api):
        uv run python poller.py           # runs until stopped (Ctrl+C, or SIGTERM from a container)
        uv run python poller.py --once    # one pass, then exit: handy for checking it works

    Each pass ("tick") does four jobs:
      1. once a day, refresh the schedule: new games (the NBA Cup ones only get dates in December),
         changed tipoffs, and postponed games moving back to scheduled, which reopens their picks
      2. a couple of hours before tipoff, email everyone who hasn't finished their picks (step 12)
      3. while a game is on or about to start, copy the live scoreboard into it
      4. for every finished game not yet scored: fetch its box score if we don't have one, then score it
    then sleeps 30 seconds while a game is on, up to 15 minutes when nothing is.

    It's a separate process, not a task inside the api, so that running two api containers can't
    mean two pollers racing each other. Run exactly one.

    It reads cdn.nba.com through nba_api, never stats.nba.com, and never a bare http client: the
    cdn's bot protection refuses curl with a 403 even from a server it serves nba_api normally
    (see HANDOFF.md). The nba's own formats are translated here, in the parse_ functions, so
    nothing past this file has to know them.
"""
import argparse
import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR)) # so it runs from any cwd, like the harvest scripts

import requests
from nba_api.live.nba.endpoints import boxscore, scoreboard
from nba_api.live.nba.library.http import NBALiveHTTP
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import email_utils
import models
import scoring
from config import settings
from database import AsyncSessionLocal, NOT_MIGRATED, engine, has_table
from routers.games import TEAM_LOADERS
from routers.pick_categories import ensure_default_categories
from schemas import GameStatus, can_move_status

logger = logging.getLogger("poller")

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
WANTED_GAME_TYPES = {"2", "4", "5"} # same as harvest.py: regular season, playoffs, play-in
NBA_STATUS = {1: GameStatus.SCHEDULED, 2: GameStatus.LIVE, 3: GameStatus.FINAL}

ACTIVE_INTERVAL = 30 # seconds between ticks while a game is on, the cdn itself only updates every few seconds
IDLE_INTERVAL = 15 * 60 # the longest it sleeps when nothing is on
SCHEDULE_EVERY = timedelta(hours=24)
SCHEDULE_RETRY = timedelta(hours=1) # after a failed refresh, so a refusing cdn isn't hit every tick
# a game is watched from shortly before tipoff until well after it should be over (overtime, delays).
# one still not final after that is left to the schedule refresh, which carries final scores too
WATCH_BEFORE = timedelta(minutes=15)
WATCH_AFTER = timedelta(hours=5)


# --- fetching: the only code that talks to the nba. sync (nba_api uses requests), so each runs in a
# thread. tests replace these three functions instead of touching the network ---

def fetch_scoreboard() -> dict:
    return scoreboard.ScoreBoard(timeout=20).get_dict()


def fetch_box_score(game_id: str) -> dict:
    return boxscore.BoxScore(game_id, timeout=20).get_dict()


def fetch_schedule() -> dict:
    # nba_api doesn't wrap the schedule file, so it gets nba_api's headers by hand
    response = requests.get(SCHEDULE_URL, headers=NBALiveHTTP.headers, timeout=30)
    response.raise_for_status()
    return response.json()


# --- parsing: the nba's formats in, our fields out. pure functions, tested against real payloads ---

def iso_clock(value: str | None) -> str | None:
    """The cdn's clocks and minutes are iso durations: "PT02M30.00S" -> "2:30".

    Seen in real data: "PT12M000.00S" at the start of a quarter, three digits of seconds.
    """
    if not value or not value.startswith("PT"):
        return value or None
    minutes, _, seconds = value[2:].partition("M")
    seconds = seconds.rstrip("S").split(".")[0] or "0"
    return f"{int(minutes or 0)}:{int(seconds):02d}"


def game_status(raw_status: int, status_text: str, postponed_status: str | None = None) -> GameStatus:
    text = (status_text or "").lower()
    # the schedule's postponedStatus is "N" on every game seen so far, so any other value is read as
    # postponed. unverified against a real postponement, hence the status text check as well
    if postponed_status not in (None, "", "N") or "ppd" in text or "postpone" in text:
        return GameStatus.POSTPONED
    return NBA_STATUS.get(raw_status, GameStatus.SCHEDULED)


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_scoreboard(payload: dict) -> dict[str, dict]:
    """Today's games, league-wide, keyed by game id. Only fields the live feed is the best source for."""
    updates = {}
    for game in payload["scoreboard"]["games"]:
        status = game_status(game["gameStatus"], game["gameStatusText"])
        updates[game["gameId"]] = {
            "status": status,
            "status_text": game["gameStatusText"].strip(), # the feed pads it with trailing spaces
            "home_score": game["homeTeam"]["score"] if status != GameStatus.SCHEDULED else None,
            "away_score": game["awayTeam"]["score"] if status != GameStatus.SCHEDULED else None,
            "period": game["period"] or None,
            "game_clock": iso_clock(game["gameClock"]) if status == GameStatus.LIVE else None,
        }
    return updates


def parse_box_score(payload: dict) -> tuple[GameStatus, list[dict]]:
    """The box score's own status, and one line per player in the same shape harvest.py writes.

    Unlike the stats.nba.com box score harvest.py reads, this one leaves inactive players out
    entirely and marks a benched player with played "0" and a minutes of "PT00M00.00S" rather
    than no minutes. Both become minutes None here, which is what "didn't appear" means to scoring.
    """
    game = payload["game"]
    status = game_status(game["gameStatus"], game["gameStatusText"])
    lines = []
    for side in ("homeTeam", "awayTeam"):
        for player in game[side]["players"]:
            stats = player["statistics"]
            appeared = player.get("played") == "1" and player.get("status") == "ACTIVE"
            lines.append({
                "game_id": game["gameId"],
                "player_id": player["personId"],
                "team_id": game[side]["teamId"],
                "first_name": player["firstName"],
                "last_name": player["familyName"],
                "jersey_number": player.get("jerseyNum") or None,
                "position": player.get("position") or None,
                "minutes": iso_clock(stats["minutes"]) if appeared else None,
                "comment": None if appeared else (player.get("notPlayingReason") or "Did not play"),
                "points": stats["points"],
                "rebounds_offensive": stats["reboundsOffensive"],
                "rebounds_defensive": stats["reboundsDefensive"],
                "rebounds_total": stats["reboundsTotal"],
                "assists": stats["assists"],
                "steals": stats["steals"],
                "blocks": stats["blocks"],
                "turnovers": stats["turnovers"],
                "three_pointers_made": stats["threePointersMade"],
            })
    return status, lines


def parse_schedule(payload: dict, tricode: str) -> list[dict]:
    """The followed team's games for the season, in the same shape harvest.py writes."""
    schedule = payload["leagueSchedule"]
    games = []
    for day in schedule["gameDates"]:
        for game in day["games"]:
            if game["gameId"][2:3] not in WANTED_GAME_TYPES:
                continue
            if tricode not in (game["homeTeam"]["teamTricode"], game["awayTeam"]["teamTricode"]):
                continue
            status = game_status(game["gameStatus"], game["gameStatusText"], game.get("postponedStatus"))
            # scores only once final: the schedule file shows a game in progress as 0-0 (seen in real
            # data), live scores come from the scoreboard
            final = status == GameStatus.FINAL
            games.append({
                "game_id": game["gameId"],
                "season": schedule["seasonYear"],
                "tipoff_utc": utc(game["gameDateTimeUTC"]),
                "status": status,
                "status_text": (game["gameStatusText"] or "").strip(),
                "home_team_id": game["homeTeam"]["teamId"],
                "away_team_id": game["awayTeam"]["teamId"],
                "home_score": game["homeTeam"]["score"] if final else None,
                "away_score": game["awayTeam"]["score"] if final else None,
                "arena_name": game["arenaName"] or None,
            })
    return games


# --- applying: our fields into the database ---

async def apply_live(db: AsyncSession, updates: dict[str, dict], now: datetime) -> list[str]:
    """Copy the scoreboard into our games it covers. Returns the ids of games it changed."""
    if not updates:
        return []
    games = (await db.execute(select(models.Game).where(models.Game.game_id.in_(updates)))).scalars().all()
    changed = []
    for game in games:
        update = updates[game.game_id]
        if game.status == GameStatus.FINAL or not can_move_status(game.status, update["status"]):
            continue # a finished game is settled, and a stale feed mustn't reopen anything
        for field, value in update.items():
            setattr(game, field, value)
        if update["status"] == GameStatus.FINAL:
            game.final_at = now # seen going final live, so its chat room closes a few hours from now
        changed.append(game.game_id)
    await db.commit()
    return changed


async def apply_schedule(db: AsyncSession, games: list[dict]) -> dict[str, int]:
    """Insert new games, move dates and statuses on existing ones. Finished games are left alone."""
    team_ids = set((await db.execute(select(models.Team.team_id))).scalars())
    existing = {g.game_id: g for g in (await db.execute(select(models.Game))).scalars()}
    counts = {"created": 0, "updated": 0, "skipped": 0}

    for fields in games:
        if not {fields["home_team_id"], fields["away_team_id"]} <= team_ids:
            logger.warning("schedule: game %s has a team not in the database, skipped", fields["game_id"])
            counts["skipped"] += 1
            continue

        game = existing.get(fields["game_id"])
        if game is None:
            db.add(models.Game(**fields))
            counts["created"] += 1
            continue
        if game.status == GameStatus.FINAL:
            continue

        # dates and places: the schedule is the authority, this is how a rescheduled game moves.
        # a moved game gets reminded again for its new date
        if game.tipoff_utc != fields["tipoff_utc"]:
            game.reminder_sent_at = None
        game.tipoff_utc = fields["tipoff_utc"]
        game.arena_name = fields["arena_name"]
        if can_move_status(game.status, fields["status"]) and fields["status"] != game.status:
            game.status = fields["status"]
            game.status_text = fields["status_text"]
            if fields["status"] == GameStatus.FINAL:
                # the backstop for a game the poller missed entirely: final scores arrive this way.
                # final_at stays None, so its chat room is closed: it may have ended days ago
                game.home_score, game.away_score = fields["home_score"], fields["away_score"]
                game.period = game.game_clock = None
        elif game.status in (GameStatus.SCHEDULED, GameStatus.POSTPONED):
            game.status_text = fields["status_text"] # "7:30 pm ET" changes when the tipoff does
        counts["updated"] += 1

    await db.commit()
    return counts


async def ingest_box_score(db: AsyncSession, lines: list[dict]) -> int:
    """Upsert one game's stat lines, creating any player we haven't seen.

    Also moves each player who appeared to the team they appeared for. There's no roster feed the
    cloud can reach, so this is how a trade shows up. Finished games are ingested oldest first,
    so the newest game's team is the one that sticks.
    """
    if not lines:
        return 0
    game_id = lines[0]["game_id"]
    stats = {
        s.player_id: s for s in (await db.execute(
            select(models.PlayerGameStat).where(models.PlayerGameStat.game_id == game_id),
        )).scalars()
    }
    player_ids = [line["player_id"] for line in lines]
    players = {
        p.player_id: p for p in (await db.execute(
            select(models.Player).where(models.Player.player_id.in_(player_ids)),
        )).scalars()
    }

    for line in lines:
        player = players.get(line["player_id"])
        if player is None:
            full_name = f"{line['first_name']} {line['last_name']}".strip()
            player = models.Player(
                player_id=line["player_id"], full_name=full_name,
                first_name=line["first_name"] or full_name, last_name=line["last_name"] or full_name,
                jersey_number=line["jersey_number"], position=line["position"],
            )
            db.add(player)
            players[player.player_id] = player
        if line["minutes"] is not None:
            player.team_id = line["team_id"]

        fields = {k: v for k, v in line.items() if k not in ("first_name", "last_name", "jersey_number", "position")}
        stat = stats.get(line["player_id"])
        if stat is None:
            db.add(models.PlayerGameStat(**fields))
        else:
            for field, value in fields.items():
                setattr(stat, field, value)

    await db.commit()
    return len(lines)


# --- reminders (step 12) ---

def reminder_lead() -> timedelta:
    return timedelta(hours=settings.reminder_hours_before)


def reminder_due(game: models.Game, now: datetime) -> bool:
    """Not yet reminded, still open, and inside the window before tipoff.

    A poller that was off when the window opened still sends late ones, as long as picks are open.
    """
    return (
        game.status == GameStatus.SCHEDULED
        and game.reminder_sent_at is None
        and game.tipoff_utc - reminder_lead() <= now < game.tipoff_utc
    )


async def send_reminders(db: AsyncSession, game: models.Game, now: datetime) -> int:
    """Email every user with reminders on who is missing at least one active pick for this game.

    The game is marked reminded before anything is sent: at most once, not at least once. A crash
    mid-way means some fans miss one reminder, the alternative is everyone getting it twice.
    Returns how many emails were sent.
    """
    categories = (await db.execute(
        select(models.PickCategory).where(models.PickCategory.is_active)
        .order_by(models.PickCategory.sort_order, models.PickCategory.pick_category_id),
    )).scalars().all()
    users = (await db.execute(
        select(models.User).where(models.User.email_reminders).order_by(models.User.user_id),
    )).scalars().all()
    made = {(user_id, category_id) for user_id, category_id in await db.execute(
        select(models.Pick.user_id, models.Pick.pick_category_id).where(models.Pick.game_id == game.game_id),
    )}

    # everything the emails need, read before the commit below so nothing has to load afterwards
    matchup = f"{game.away_team.full_name} at {game.home_team.full_name}"
    game_id, tipoff_utc = game.game_id, game.tipoff_utc
    outbox = []
    for user in users:
        missing = [c.name for c in categories if (user.user_id, c.pick_category_id) not in made]
        if missing: # all picks in means nothing to remind them of
            outbox.append((user.user_id, user.email, user.username, missing))

    game.reminder_sent_at = now
    await db.commit()

    sent = 0
    for user_id, email, username, missing in outbox:
        try:
            await email_utils.send_pick_reminder_email(email, username, matchup, tipoff_utc, game_id, missing)
            sent += 1
        except Exception as err:
            # one bad address or a hiccup at the smtp server mustn't stop the others, or the poller
            logger.error("reminder to user %d for %s failed (%s: %s)", user_id, game_id, type(err).__name__, err)
    return sent


# --- the tick ---

@dataclass
class PollerState:
    last_schedule_attempt: datetime | None = None
    last_schedule_ok: bool = False

    def schedule_due(self, now: datetime) -> bool:
        if self.last_schedule_attempt is None:
            return True
        wait = SCHEDULE_EVERY if self.last_schedule_ok else SCHEDULE_RETRY
        return now - self.last_schedule_attempt >= wait


async def fetch(label: str, call, *args):
    """Run a fetch in a thread. None when it fails, logged loudly: a refusal from the nba is the
    first sign its bot rules changed, and one failed fetch must never stop the poller."""
    try:
        return await asyncio.to_thread(call, *args)
    except Exception as err:
        logger.error("%s: the nba refused or failed (%s: %s)", label, type(err).__name__, str(err)[:200])
        return None


def watched(game: models.Game, now: datetime) -> bool:
    if game.status == GameStatus.LIVE:
        return True
    return game.status == GameStatus.SCHEDULED and now - WATCH_AFTER <= game.tipoff_utc <= now + WATCH_BEFORE


async def tick(db: AsyncSession, now: datetime, state: PollerState) -> int:
    """One pass of the four jobs. Returns how many seconds to sleep before the next."""

    # 1. the schedule, daily
    if state.schedule_due(now):
        state.last_schedule_attempt = now
        payload = await fetch("schedule", fetch_schedule)
        state.last_schedule_ok = payload is not None
        if payload is not None:
            counts = await apply_schedule(db, parse_schedule(payload, settings.team_tricode))
            logger.info("schedule: %(created)d new, %(updated)d updated, %(skipped)d skipped", counts)

    # 2. pick reminders, after the schedule so a moved tipoff is already known
    upcoming = (await db.execute(
        select(models.Game).options(*TEAM_LOADERS)
        .where(models.Game.status == GameStatus.SCHEDULED, models.Game.reminder_sent_at.is_(None))
        .order_by(models.Game.tipoff_utc),
    )).scalars().all()
    for game in upcoming:
        if reminder_due(game, now):
            logger.info("reminders for %s: %d sent", game.game_id, await send_reminders(db, game, now))

    # 3. live scores, only when one of our games is on or about to be
    games = (await db.execute(
        select(models.Game).where(models.Game.status.in_([GameStatus.SCHEDULED, GameStatus.LIVE])),
    )).scalars().all()
    if any(watched(game, now) for game in games):
        payload = await fetch("scoreboard", fetch_scoreboard)
        if payload is not None:
            changed = await apply_live(db, parse_scoreboard(payload), now)
            if changed:
                logger.info("scoreboard: updated %s", ", ".join(changed))

    # 4. finished games not yet scored, oldest first (see ingest_box_score for why the order matters)
    pending = (await db.execute(
        select(models.Game).options(*TEAM_LOADERS)
        .where(models.Game.status == GameStatus.FINAL, models.Game.scored_at.is_(None))
        .order_by(models.Game.tipoff_utc),
    )).scalars().all()
    for game in pending:
        has_box_score = (await db.execute(
            select(func.count()).select_from(models.PlayerGameStat).where(models.PlayerGameStat.game_id == game.game_id),
        )).scalar()
        if not has_box_score:
            payload = await fetch(f"box score {game.game_id}", fetch_box_score, game.game_id)
            if payload is None:
                continue # tried again next tick
            status, lines = parse_box_score(payload)
            if status != GameStatus.FINAL:
                continue # the scoreboard can say final a moment before the box score does
            logger.info("box score %s: %d lines", game.game_id, await ingest_box_score(db, lines))
        try:
            report = await scoring.score_game(db, game)
            logger.info("scored %s (%s by %d): %d picks", game.game_id, report.winner, report.margin, report.picks_scored)
        except scoring.ScoringError as err:
            logger.warning("couldn't score %s: %s", game.game_id, err)

    return next_interval(
        (await db.execute(
            select(models.Game).where(models.Game.status.in_([GameStatus.SCHEDULED, GameStatus.LIVE])),
        )).scalars().all(),
        now,
    )


def next_interval(open_games: list[models.Game], now: datetime) -> int:
    """30 seconds while a game is watched, otherwise until the next thing to do: a game's watch
    starting, or its reminders coming due (at most 15 minutes)."""
    if any(watched(game, now) for game in open_games):
        return ACTIVE_INTERVAL
    scheduled = [g for g in open_games if g.status == GameStatus.SCHEDULED and g.tipoff_utc > now]
    upcoming = [g.tipoff_utc - WATCH_BEFORE for g in scheduled]
    upcoming += [
        g.tipoff_utc - reminder_lead() for g in scheduled
        if g.reminder_sent_at is None and g.tipoff_utc - reminder_lead() > now
    ]
    if not upcoming:
        return IDLE_INTERVAL
    until = (min(upcoming) - now).total_seconds()
    return int(min(IDLE_INTERVAL, max(ACTIVE_INTERVAL, until)))


# --- running it ---

async def run(once: bool = False) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set) # a container stop finishes the tick in progress first
        except NotImplementedError:
            pass # windows: Ctrl+C still works, it just interrupts mid-tick

    # tables come from the migrations, which may not have run yet on a fresh database
    if not await has_table("games"):
        logger.error(NOT_MIGRATED)
        await engine.dispose()
        return
    async with AsyncSessionLocal() as db:
        await ensure_default_categories(db)

    state = PollerState()
    logger.info("poller started, following %s", settings.team_tricode)
    while not stop.is_set():
        try:
            async with AsyncSessionLocal() as db:
                interval = await tick(db, datetime.now(UTC), state)
        except Exception:
            # a database error, a bug: log it and try again shortly rather than dying
            logger.exception("tick failed")
            interval = 60
        if once:
            break
        logger.info("next tick in %ds", interval)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            pass

    await engine.dispose()
    logger.info("poller stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Keep the database in step with real NBA games.")
    parser.add_argument("--once", action="store_true", help="run a single tick, then exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        asyncio.run(run(once=args.once))
    except KeyboardInterrupt:
        pass
