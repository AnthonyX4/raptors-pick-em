from datetime import datetime, timedelta, UTC

import pytest
from sqlalchemy import select

import models
from conftest import BOS, MIA, TOR, register_and_login
from routers import picks as picks_router

GAME = "0022600099"
TIPOFF = datetime(2027, 1, 10, 0, 30, tzinfo=UTC)
BARNES, QUICKLEY, TATUM, FREE_AGENT = 1, 2, 3, 4 # from the players fixture: two Raptors, a Celtic, nobody's


@pytest.fixture
def clock(monkeypatch):
    """Sets what time the picks router thinks it is. Starts a day before tipoff."""
    now = {"value": TIPOFF - timedelta(days=1)}
    monkeypatch.setattr(picks_router, "utcnow", lambda: now["value"])

    def set_time(value: datetime):
        now["value"] = value
    return set_time


@pytest.fixture
def game(db, teams, players, clock):
    db.add(models.Game(
        game_id=GAME, season="2026-27", tipoff_utc=TIPOFF, status="scheduled", status_text="7:30 pm ET",
        home_team_id=TOR, away_team_id=BOS, arena_name="Scotiabank Arena",
    ))
    db.commit()
    return GAME


@pytest.fixture
def category(client) -> dict:
    """Category ids by key, from the six defaults the app creates at startup."""
    return {c["key"]: c["pick_category_id"] for c in client.get("/api/pick-categories").json()}


def make(client, headers, category_id, **answer):
    return client.post("/api/picks", json={"game_id": GAME, "pick_category_id": category_id, **answer}, headers=headers)


def pick_winner(client, headers, category, team_id=TOR) -> dict:
    response = make(client, headers, category["winner"], team_id=team_id)
    assert response.status_code == 201, response.text
    return response.json()


def set_game(db, **fields):
    game = db.get(models.Game, GAME)
    for name, value in fields.items():
        setattr(game, name, value)
    db.commit()


# --- making picks ---

def test_make_a_winner_pick(client, user_headers, game, category):
    pick = pick_winner(client, user_headers, category)
    assert pick["category"]["key"] == "winner"
    assert pick["team"]["tricode"] == "TOR"
    assert pick["player"] is None
    assert pick["points_awarded"] is None # not scored until step 7


def test_winner_must_be_one_of_the_two_teams(client, user_headers, game, category):
    response = make(client, user_headers, category["winner"], team_id=MIA)
    assert response.status_code == 400
    assert response.json()["detail"] == "Pick one of the two teams in this game"


@pytest.mark.parametrize("answer", [
    {"player_id": BARNES}, # the wrong field for a winner
    {"team_id": TOR, "margin": 5}, # the right field plus another
    {}, # nothing
])
def test_a_pick_fills_in_exactly_its_own_field(client, user_headers, game, category, answer):
    response = make(client, user_headers, category["winner"], **answer)
    assert response.status_code == 400
    assert response.json()["detail"] == "A 'Winner' pick needs team_id and nothing else"


def test_bonus_picks_need_the_winner_pick_first(client, user_headers, game, category):
    response = make(client, user_headers, category["leader:points"], player_id=BARNES)
    assert response.status_code == 409
    assert response.json()["detail"] == "Make your Winner pick first"


def test_stat_leader_pick_after_the_winner(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    response = make(client, user_headers, category["leader:points"], player_id=BARNES)
    assert response.status_code == 201
    assert response.json()["player"]["full_name"] == "Scottie Barnes"
    assert response.json()["player"]["team"]["tricode"] == "TOR"


@pytest.mark.parametrize("player_id", [TATUM, FREE_AGENT, 999])
def test_stat_leader_must_be_a_raptor(client, user_headers, game, category, player_id):
    # decided: "Raptors' top scorer", so a Celtic, a player on no roster, or nobody at all is refused
    pick_winner(client, user_headers, category)
    response = make(client, user_headers, category["leader:points"], player_id=player_id)
    assert response.status_code == 400
    assert response.json()["detail"] == "Pick a player on the TOR roster"


def test_margin_pick(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    response = make(client, user_headers, category["margin"], margin=7)
    assert response.status_code == 201
    assert response.json()["margin"] == 7


@pytest.mark.parametrize("margin", [0, -3, 100])
def test_margin_out_of_range_is_422(client, user_headers, game, category, margin):
    pick_winner(client, user_headers, category)
    assert make(client, user_headers, category["margin"], margin=margin).status_code == 422


def test_one_pick_per_category_per_game(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    response = make(client, user_headers, category["winner"], team_id=BOS)
    assert response.status_code == 409
    assert response.json()["detail"] == "You already have a pick in this category, edit it instead"


def test_two_users_can_pick_the_same_category(client, user_headers, game, category):
    other = register_and_login(client, "other@example.com")
    pick_winner(client, user_headers, category)
    pick_winner(client, other, category, team_id=BOS)


def test_deactivated_category_takes_no_new_picks(client, user_headers, admin_headers, game, category):
    pick_winner(client, user_headers, category)
    client.patch(f"/api/admin/pick-categories/{category['margin']}", json={"is_active": False}, headers=admin_headers)

    response = make(client, user_headers, category["margin"], margin=5)
    assert response.status_code == 400
    assert response.json()["detail"] == "This category isn't open for picks"


def test_unknown_game_and_category_are_404(client, user_headers, game, category):
    response = client.post("/api/picks", json={"game_id": "0000000000", "pick_category_id": category["winner"], "team_id": TOR}, headers=user_headers)
    assert response.status_code == 404
    response = client.post("/api/picks", json={"game_id": GAME, "pick_category_id": 999, "team_id": TOR}, headers=user_headers)
    assert response.status_code == 404


def test_picking_needs_a_token(client, game, category):
    assert make(client, {}, category["winner"], team_id=TOR).status_code == 401


# --- editing and withdrawing ---

def test_edit_a_pick(client, user_headers, game, category):
    pick = pick_winner(client, user_headers, category)
    response = client.patch(f"/api/picks/{pick['pick_id']}", json={"team_id": BOS}, headers=user_headers)
    assert response.status_code == 200
    assert response.json()["team"]["tricode"] == "BOS"
    assert response.json()["updated_at"] >= pick["updated_at"]


def test_an_edit_follows_the_same_answer_rules(client, user_headers, game, category):
    pick = pick_winner(client, user_headers, category)
    assert client.patch(f"/api/picks/{pick['pick_id']}", json={"team_id": MIA}, headers=user_headers).status_code == 400
    assert client.patch(f"/api/picks/{pick['pick_id']}", json={"player_id": BARNES}, headers=user_headers).status_code == 400


def test_withdraw_a_bonus_pick(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    bonus = make(client, user_headers, category["leader:points"], player_id=BARNES).json()

    assert client.delete(f"/api/picks/{bonus['pick_id']}", headers=user_headers).status_code == 204
    assert client.get("/api/picks/me", headers=user_headers).json()["total"] == 1


def test_the_winner_pick_goes_last(client, user_headers, game, category):
    winner = pick_winner(client, user_headers, category)
    bonus = make(client, user_headers, category["leader:points"], player_id=BARNES).json()

    response = client.delete(f"/api/picks/{winner['pick_id']}", headers=user_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Withdraw your other picks for this game before your Winner pick"

    assert client.delete(f"/api/picks/{bonus['pick_id']}", headers=user_headers).status_code == 204
    assert client.delete(f"/api/picks/{winner['pick_id']}", headers=user_headers).status_code == 204


def test_someone_elses_pick_is_404_for_edit_and_withdraw(client, user_headers, game, category):
    pick = pick_winner(client, user_headers, category)
    other = register_and_login(client, "other@example.com")

    assert client.patch(f"/api/picks/{pick['pick_id']}", json={"team_id": BOS}, headers=other).status_code == 404
    assert client.delete(f"/api/picks/{pick['pick_id']}", headers=other).status_code == 404


# --- the tipoff lock ---

def test_everything_locks_at_tipoff(client, user_headers, game, category, clock):
    pick = pick_winner(client, user_headers, category)
    clock(TIPOFF) # the exact moment counts as started

    assert make(client, user_headers, category["margin"], margin=5).status_code == 409
    assert client.patch(f"/api/picks/{pick['pick_id']}", json={"team_id": BOS}, headers=user_headers).status_code == 409
    assert client.delete(f"/api/picks/{pick['pick_id']}", headers=user_headers).status_code == 409


def test_open_one_second_before_tipoff(client, user_headers, game, category, clock):
    clock(TIPOFF - timedelta(seconds=1))
    pick_winner(client, user_headers, category)


@pytest.mark.parametrize("status", ["live", "final"])
def test_a_started_game_is_locked_whatever_the_clock_says(client, user_headers, game, category, db, status):
    set_game(db, status=status) # the poller marked it live early, or the tipoff time was wrong
    response = make(client, user_headers, category["winner"], team_id=TOR)
    assert response.status_code == 409
    assert response.json()["detail"] == "Picks for this game are locked"


# --- hidden until tipoff ---

def test_picks_are_hidden_before_tipoff(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    response = client.get("/api/picks", params={"game_id": GAME})
    assert response.status_code == 403
    assert response.json()["detail"] == "Picks are revealed at tipoff"


def test_picks_are_revealed_at_tipoff_with_their_authors(client, user_headers, game, category, clock):
    other = register_and_login(client, "other@example.com")
    pick_winner(client, user_headers, category)
    make(client, user_headers, category["leader:points"], player_id=BARNES)
    pick_winner(client, other, category, team_id=BOS)

    clock(TIPOFF)
    page = client.get("/api/picks", params={"game_id": GAME}).json() # no token needed once revealed
    assert page["total"] == 3
    assert [(p["user"]["username"], p["category"]["key"]) for p in page["picks"]] == [
        ("customer", "winner"), ("customer", "leader:points"), ("other", "winner"),
    ]
    assert "email" not in page["picks"][0]["user"] # authors are public profiles, not private ones


def test_revealed_picks_unknown_game_is_404(client, game):
    assert client.get("/api/picks", params={"game_id": "0000000000"}).status_code == 404


# --- postponed games (decided: keep the picks, reopen on the new date) ---

def test_a_postponed_game_is_locked_and_stays_hidden(client, user_headers, game, category, db, clock):
    pick_winner(client, user_headers, category)
    set_game(db, status="postponed", status_text="PPD")
    clock(TIPOFF + timedelta(hours=3)) # the original tipoff has passed

    assert make(client, user_headers, category["margin"], margin=5).status_code == 409
    # closed but never played: revealing now would let people copy picks before the new date
    assert client.get("/api/picks", params={"game_id": GAME}).status_code == 403


def test_a_rescheduled_game_reopens_with_its_picks(client, user_headers, game, category, db, clock):
    pick = pick_winner(client, user_headers, category)
    set_game(db, status="postponed")
    clock(TIPOFF + timedelta(days=1))

    set_game(db, status="scheduled", tipoff_utc=TIPOFF + timedelta(days=20)) # what the schedule refresh will do
    mine = client.get("/api/picks/me", headers=user_headers).json()["picks"]
    assert [p["pick_id"] for p in mine] == [pick["pick_id"]] # carried over
    assert client.patch(f"/api/picks/{pick['pick_id']}", json={"team_id": BOS}, headers=user_headers).status_code == 200


# --- my picks ---

def test_my_picks_newest_game_first_then_form_order(client, user_headers, game, category, db, clock):
    later = "0022600100"
    db.add(models.Game(
        game_id=later, season="2026-27", tipoff_utc=TIPOFF + timedelta(days=2), status="scheduled",
        home_team_id=BOS, away_team_id=TOR,
    ))
    db.commit()
    pick_winner(client, user_headers, category)
    make(client, user_headers, category["leader:points"], player_id=BARNES)
    client.post("/api/picks", json={"game_id": later, "pick_category_id": category["winner"], "team_id": TOR}, headers=user_headers)

    page = client.get("/api/picks/me", headers=user_headers).json()
    assert [(p["game_id"], p["category"]["key"]) for p in page["picks"]] == [
        (later, "winner"), (GAME, "winner"), (GAME, "leader:points"),
    ]

    only_one = client.get("/api/picks/me", params={"game_id": GAME}, headers=user_headers).json()
    assert only_one["total"] == 2


def test_my_picks_are_only_mine(client, user_headers, game, category):
    other = register_and_login(client, "other@example.com")
    pick_winner(client, other, category)
    assert client.get("/api/picks/me", headers=user_headers).json()["total"] == 0


def test_my_picks_paginate(client, user_headers, game, category):
    pick_winner(client, user_headers, category)
    make(client, user_headers, category["margin"], margin=3)
    make(client, user_headers, category["leader:points"], player_id=BARNES)

    page = client.get("/api/picks/me", params={"limit": 2}, headers=user_headers).json()
    assert len(page["picks"]) == 2
    assert page["total"] == 3
    assert page["has_more"] is True


# --- account deletion (decided: picks go with the account) ---

def test_deleting_an_account_deletes_its_picks(client, user_headers, game, category, db):
    pick_winner(client, user_headers, category)
    make(client, user_headers, category["leader:points"], player_id=BARNES)
    me = client.get("/api/users/me", headers=user_headers).json()

    assert client.delete(f"/api/users/{me['user_id']}", headers=user_headers).status_code == 204
    assert db.execute(select(models.Pick)).scalars().all() == []
