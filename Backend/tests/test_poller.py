import asyncio
import copy
import json
import sys
from datetime import datetime, timedelta, UTC
from pathlib import Path

import pytest
from nba_api.stats.static import teams as static_teams
from sqlalchemy import select

import models
import poller
from conftest import BACKEND_DIR, TestAsyncSession
from routers.pick_categories import ensure_default_categories
from schemas import GameStatus

sys.path.insert(0, str(BACKEND_DIR / "harvest_scripts"))
import seed

# real payloads captured from cdn.nba.com by .github/workflows/capture-nba-samples.yml, trimmed.
# captured while TOR @ PHI (0022600227) was in the 4th quarter
FIXTURES = Path(__file__).parent / "fixtures" / "nba"
LIVE_NOW = datetime(2026, 11, 13, 2, 20, tzinfo=UTC)
OPENER, AT_WAS, AT_MIN, AT_PHI, VS_NYK = "0022600088", "0022600097", "0022600115", "0022600227", "0022600241"
TOR, BOS = 1610612761, 1610612738
BARNES, LEONARD = 1630567, 202695


def load(name) -> dict:
    return json.loads((FIXTURES / name).read_text())


def run(work):
    """Run an async function of a session, the way the poller gets one per tick."""
    async def go():
        async with TestAsyncSession() as session:
            return await work(session)
    return asyncio.run(go())


@pytest.fixture
def league(db):
    """All 30 teams (offline, from nba_api's dataset) and the default pick categories."""
    db.add_all(
        models.Team(team_id=t["id"], tricode=t["abbreviation"], city=t["city"], nickname=t["nickname"], full_name=t["full_name"])
        for t in static_teams.get_teams()
    )
    db.commit()
    run(ensure_default_categories)


@pytest.fixture
def nba(monkeypatch):
    """Fakes the three fetches. Each serves a real payload by default and records its calls.

    Set nba.schedule / nba.scoreboard to another payload, or to an exception to raise.
    nba.box_scores maps game id -> payload; a game not in it raises like a refused fetch.
    """
    class FakeNBA:
        schedule = load("schedule.json")
        scoreboard = load("scoreboard.json")
        box_scores = {OPENER: load("boxscore_0022600088.json")}
        calls = []

        def serve(self, label, value):
            self.calls.append(label)
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)

    fake = FakeNBA()
    fake.calls = []
    monkeypatch.setattr(poller, "fetch_schedule", lambda: fake.serve("schedule", fake.schedule))
    monkeypatch.setattr(poller, "fetch_scoreboard", lambda: fake.serve("scoreboard", fake.scoreboard))
    monkeypatch.setattr(poller, "fetch_box_score", lambda game_id: fake.serve(
        f"box score {game_id}", fake.box_scores.get(game_id, ConnectionError("403 Access Denied"))))
    return fake


def tick(now=LIVE_NOW, state=None) -> int:
    state = state if state is not None else poller.PollerState()
    return run(lambda db: poller.tick(db, now, state))


def game(db, game_id) -> models.Game:
    db.expire_all() # the poller wrote through another connection
    return db.get(models.Game, game_id)


# --- parsing real payloads ---

def test_scoreboard_parses_a_live_game():
    update = poller.parse_scoreboard(load("scoreboard.json"))[AT_PHI]
    assert update == {
        "status": GameStatus.LIVE, "status_text": "4th Qtr", # the feed pads it with spaces
        "home_score": 118, "away_score": 108, "period": 4, "game_clock": "2:30",
    }


@pytest.mark.parametrize("raw,expected", [
    ("PT02M30.00S", "2:30"), ("PT12M000.00S", "12:00"), ("PT00M00.00S", "0:00"), ("", None), (None, None),
])
def test_iso_clock(raw, expected):
    assert poller.iso_clock(raw) == expected


def test_box_score_lines():
    status, lines = poller.parse_box_score(load("boxscore_0022600088.json"))
    assert status == GameStatus.FINAL
    assert len(lines) == 28 # active players only, the cdn leaves inactive ones out
    leonard = next(l for l in lines if l["player_id"] == LEONARD)
    assert (leonard["team_id"], leonard["minutes"], leonard["points"], leonard["steals"]) == (TOR, "23:56", 23, 4)


def test_a_benched_player_did_not_appear():
    # played "0" with minutes "PT00M00.00S": zero minutes must not read as having played
    _, lines = poller.parse_box_score(load("boxscore_0022600088.json"))
    benched = next(l for l in lines if l["last_name"] == "Williams")
    assert (benched["minutes"], benched["comment"]) == (None, "Did not play")


def test_schedule_keeps_only_the_teams_real_games():
    games = poller.parse_schedule(load("schedule.json"), "TOR")
    assert [g["game_id"] for g in games] == [OPENER, AT_WAS, AT_MIN, AT_PHI, VS_NYK, "0022600253", "0022600263"] # no preseason
    opener = games[0]
    assert (opener["status"], opener["home_score"], opener["away_score"]) == (GameStatus.FINAL, 135, 92)
    assert opener["tipoff_utc"] == datetime(2026, 10, 21, 23, 30, tzinfo=UTC)


def test_schedule_gives_no_score_for_a_game_in_progress():
    # the schedule file shows a live game as 0-0, which must not overwrite a real live score
    at_phi = next(g for g in poller.parse_schedule(load("schedule.json"), "TOR") if g["game_id"] == AT_PHI)
    assert (at_phi["status"], at_phi["home_score"]) == (GameStatus.LIVE, None)


@pytest.mark.parametrize("raw,text,postponed,expected", [
    (1, "7:00 pm ET", "N", GameStatus.SCHEDULED),
    (1, "7:00 pm ET", "Y", GameStatus.POSTPONED),
    (1, "PPD", None, GameStatus.POSTPONED),
    (2, "Q3 4:12", None, GameStatus.LIVE),
    (3, "Final", "N", GameStatus.FINAL),
])
def test_game_status(raw, text, postponed, expected):
    assert poller.game_status(raw, text, postponed) == expected


# --- ticks ---

def test_first_tick_loads_the_schedule_then_waits_a_day(db, league, nba):
    state = poller.PollerState()
    tick(state=state)
    db.expire_all()
    assert db.execute(select(models.Game)).scalars().all().__len__() == 7

    tick(LIVE_NOW + timedelta(hours=23), state)
    assert nba.calls.count("schedule") == 1
    tick(LIVE_NOW + timedelta(hours=24), state)
    assert nba.calls.count("schedule") == 2


def test_a_live_game_gets_the_scoreboard(db, league, nba):
    interval = tick()
    at_phi = game(db, AT_PHI)
    assert (at_phi.status, at_phi.home_score, at_phi.away_score, at_phi.period, at_phi.game_clock) == ("live", 118, 108, 4, "2:30")
    assert interval == poller.ACTIVE_INTERVAL


def test_a_finished_game_is_box_scored_and_its_picks_scored(db, league, nba):
    user = models.User(username="fan", email="fan@example.com", password_hash="x")
    db.add(user)
    db.commit()
    tick() # loads the schedule: the opener arrives final, with no box score yet
    cat = {c.key: c.pick_category_id for c in db.execute(select(models.PickCategory)).scalars()}
    db.add_all([
        models.Pick(user_id=user.user_id, game_id=OPENER, pick_category_id=cat["winner"], team_id=TOR),
        models.Pick(user_id=user.user_id, game_id=OPENER, pick_category_id=cat["leader:points"], player_id=BARNES),
    ])
    db.commit()
    db.execute(select(models.Game).where(models.Game.game_id == OPENER)).scalars().one().scored_at = None
    db.commit()

    tick()
    assert f"box score {OPENER}" in nba.calls
    assert game(db, OPENER).scored_at is not None
    points = sorted(p.points_awarded for p in db.execute(select(models.Pick)).scalars())
    assert points == [1, 2] # TOR won; Barnes tied Leonard and Quickley on 23


def test_a_refused_box_score_is_retried_without_stopping_anything(db, league, nba):
    tick() # the two other finished games have no box score the fake will serve
    assert game(db, AT_WAS).scored_at is None
    assert game(db, OPENER).scored_at is not None # the one that could be fetched still got scored

    nba.box_scores[AT_WAS] = load("boxscore_0022600088.json") # stand-in content, the game id is what matters
    nba.box_scores[AT_WAS]["game"]["gameId"] = AT_WAS
    tick()
    assert game(db, AT_WAS).scored_at is not None


def test_a_game_that_already_has_a_box_score_is_not_fetched_again(db, league, nba):
    _, lines = poller.parse_box_score(load("boxscore_0022600088.json"))
    run(lambda s: poller.apply_schedule(s, poller.parse_schedule(load("schedule.json"), "TOR")))
    run(lambda s: poller.ingest_box_score(s, lines)) # what the seed does for harvested games

    tick()
    assert f"box score {OPENER}" not in nba.calls
    assert game(db, OPENER).scored_at is not None


def test_a_stale_feed_never_moves_a_game_backwards(db, league, nba):
    tick()
    nba.scoreboard = load("scoreboard.json")
    phi = next(g for g in nba.scoreboard["scoreboard"]["games"] if g["gameId"] == AT_PHI)
    phi.update(gameStatus=3, gameStatusText="Final")
    tick()
    assert game(db, AT_PHI).status == "final"

    phi.update(gameStatus=2, gameStatusText="4th Qtr") # an older copy of the feed arrives
    phi["homeTeam"]["score"] = 1
    tick()
    at_phi = game(db, AT_PHI)
    assert (at_phi.status, at_phi.home_score) == ("final", 118)


def test_postponed_game_reopens_on_its_new_date(db, league, nba):
    state = poller.PollerState()
    nba.schedule = load("schedule.json")
    nyk = next(g for d in nba.schedule["leagueSchedule"]["gameDates"] for g in d["games"] if g["gameId"] == VS_NYK)
    nyk["postponedStatus"] = "Y"
    tick(state=state)
    assert game(db, VS_NYK).status == "postponed"

    nyk.update(postponedStatus="N", gameDateTimeUTC="2026-12-02T00:30:00Z", gameStatusText="7:30 pm ET")
    tick(LIVE_NOW + timedelta(days=1), state)
    nyk_game = game(db, VS_NYK)
    assert (nyk_game.status, nyk_game.tipoff_utc, nyk_game.status_text) == ("scheduled", datetime(2026, 12, 2, 0, 30, tzinfo=UTC), "7:30 pm ET")


def test_a_failed_schedule_is_retried_within_the_hour_not_the_day(db, league, nba):
    state = poller.PollerState()
    nba.schedule = ConnectionError("403 Access Denied")
    interval = tick(state=state) # nothing raised out of the tick
    assert interval > 0
    assert not state.schedule_due(LIVE_NOW + timedelta(minutes=59))
    assert state.schedule_due(LIVE_NOW + timedelta(hours=1))


def test_a_player_moves_to_the_team_he_last_played_for(db, league, nba):
    db.add(models.Player(player_id=LEONARD, full_name="Kawhi Leonard", first_name="Kawhi", last_name="Leonard", team_id=BOS))
    db.commit()
    run(lambda s: poller.apply_schedule(s, poller.parse_schedule(load("schedule.json"), "TOR")))
    _, lines = poller.parse_box_score(load("boxscore_0022600088.json"))
    run(lambda s: poller.ingest_box_score(s, lines))

    db.expire_all()
    assert db.get(models.Player, LEONARD).team_id == TOR # how a trade shows up
    assert db.get(models.Player, BARNES).full_name == "Scottie Barnes" # created from the box score


# --- sleeping ---

def make(status, tipoff):
    return models.Game(game_id="x", season="2026-27", status=status, tipoff_utc=tipoff, home_team_id=TOR, away_team_id=BOS)


@pytest.mark.parametrize("status,tipoff_in,expected", [
    ("live", timedelta(hours=-1), poller.ACTIVE_INTERVAL),
    ("scheduled", timedelta(minutes=10), poller.ACTIVE_INTERVAL), # inside the 15 minute run-up
    ("scheduled", timedelta(minutes=20), 5 * 60), # wakes for the run-up, not later
    ("scheduled", timedelta(hours=6), poller.IDLE_INTERVAL),
])
def test_next_interval(status, tipoff_in, expected):
    assert poller.next_interval([make(status, LIVE_NOW + tipoff_in)], LIVE_NOW) == expected


def test_nothing_on_sleeps_the_longest():
    assert poller.next_interval([], LIVE_NOW) == poller.IDLE_INTERVAL


# --- the seed script shares the never-backwards rule ---

def test_reseeding_an_old_file_keeps_a_newer_final_score(db, league):
    db.add(models.Game(game_id=VS_NYK, season="2026-27", tipoff_utc=LIVE_NOW, status="final",
                       status_text="Final", home_team_id=TOR, away_team_id=1610612752, home_score=110, away_score=101))
    db.commit()
    old_harvest = [{"game_id": VS_NYK, "season": "2026-27", "tipoff_utc": "2026-11-15T23:00:00+00:00",
                    "status": "scheduled", "status_text": "6:00 pm ET", "home_team_id": TOR,
                    "away_team_id": 1610612752, "home_score": None, "away_score": None, "arena_name": "Scotiabank Arena"}]

    async def reseed(s):
        await seed.seed_games(s, old_harvest)
        await s.commit()
    run(reseed)

    nyk = game(db, VS_NYK)
    assert (nyk.status, nyk.home_score, nyk.arena_name) == ("final", 110, "Scotiabank Arena")
