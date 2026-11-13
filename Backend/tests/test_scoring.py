import pytest
from sqlalchemy import select

import models
from conftest import BOS, TOR, register_and_login

GAME = "0022600001" # from the box_score fixture: TOR 115, BOS 108, so TOR by 7
BARNES, QUICKLEY, TATUM = 1, 2, 3 # Barnes 22 pts 9 reb 5 ast 2 stl; Tatum (BOS) 30 pts; Quickley did not play


@pytest.fixture
def cat(client, db) -> dict:
    """Default category ids by key. Asks for client first: the app creates them at startup."""
    return {c.key: c.pick_category_id for c in db.execute(select(models.PickCategory)).scalars()}


@pytest.fixture
def user_id(client, user_headers) -> int:
    return client.get("/api/users/me", headers=user_headers).json()["user_id"]


def add_pick(db, user_id, category_id, game=GAME, **answer) -> int:
    # straight into the database: these games are long finished, so the api would refuse new picks
    pick = models.Pick(user_id=user_id, game_id=game, pick_category_id=category_id, **answer)
    db.add(pick)
    db.commit()
    return pick.pick_id


def score(client, admin_headers, game=GAME, **params):
    return client.post(f"/api/admin/games/{game}/score", params=params, headers=admin_headers)


def points(db, pick_id):
    db.expire_all() # the api wrote these through another connection
    return db.get(models.Pick, pick_id).points_awarded


def set_line(db, player_id, **fields):
    line = db.execute(select(models.PlayerGameStat).where(
        models.PlayerGameStat.game_id == GAME, models.PlayerGameStat.player_id == player_id,
    )).scalars().one()
    for name, value in fields.items():
        setattr(line, name, value)
    db.commit()


# --- winner ---

def test_right_and_wrong_winner(client, admin_headers, box_score, cat, user_id, db):
    other_id = client.get("/api/users/me", headers=register_and_login(client, "other@example.com")).json()["user_id"]
    right = add_pick(db, user_id, cat["winner"], team_id=TOR)
    wrong = add_pick(db, other_id, cat["winner"], team_id=BOS)

    assert score(client, admin_headers).status_code == 200
    assert (points(db, right), points(db, wrong)) == (1, 0)


# --- margin (decided: wider tiers, and only if the winner pick was right) ---

@pytest.mark.parametrize("picked,expected", [
    (7, 3), # exact
    (2, 2), (12, 2), # off by 5: still two thirds
    (1, 1), (17, 1), # off by 6 and 10: one third
    (18, 0), # off by 11
])
def test_margin_tiers(client, admin_headers, box_score, cat, user_id, db, picked, expected):
    add_pick(db, user_id, cat["winner"], team_id=TOR)
    margin = add_pick(db, user_id, cat["margin"], margin=picked)

    score(client, admin_headers)
    assert points(db, margin) == expected


def test_exact_margin_with_the_wrong_winner_scores_nothing(client, admin_headers, box_score, cat, user_id, db):
    # "BOS by 7" when TOR won by 7
    add_pick(db, user_id, cat["winner"], team_id=BOS)
    margin = add_pick(db, user_id, cat["margin"], margin=7)

    score(client, admin_headers)
    assert points(db, margin) == 0


def test_margin_tiers_scale_with_a_reweighted_category(client, admin_headers, box_score, cat, user_id, db):
    client.patch(f"/api/admin/pick-categories/{cat['margin']}", json={"points": 6}, headers=admin_headers)
    add_pick(db, user_id, cat["winner"], team_id=TOR)
    margin = add_pick(db, user_id, cat["margin"], margin=2) # off by 5: two thirds of 6

    score(client, admin_headers)
    assert points(db, margin) == 4


# --- stat leaders ---

def test_the_leader_among_raptors_scores_even_when_an_opponent_did_more(client, admin_headers, box_score, cat, user_id, db):
    add_pick(db, user_id, cat["winner"], team_id=TOR)
    pick = add_pick(db, user_id, cat["leader:points"], player_id=BARNES) # 22, Tatum's 30 was for Boston

    report = score(client, admin_headers).json()
    assert points(db, pick) == 2
    assert report["leaders"]["leader:points"] == ["Scottie Barnes"]


def test_a_player_who_did_not_play_leads_nothing(client, admin_headers, box_score, cat, user_id, db):
    pick = add_pick(db, user_id, cat["leader:points"], player_id=QUICKLEY)
    score(client, admin_headers)
    assert points(db, pick) == 0


def test_every_tied_leader_counts(client, admin_headers, box_score, cat, user_id, db):
    set_line(db, QUICKLEY, minutes="30:00", comment=None, points=22) # level with Barnes
    other_id = client.get("/api/users/me", headers=register_and_login(client, "other@example.com")).json()["user_id"]
    on_barnes = add_pick(db, user_id, cat["leader:points"], player_id=BARNES)
    on_quickley = add_pick(db, other_id, cat["leader:points"], player_id=QUICKLEY)

    report = score(client, admin_headers).json()
    assert (points(db, on_barnes), points(db, on_quickley)) == (2, 2)
    assert report["leaders"]["leader:points"] == ["Immanuel Quickley", "Scottie Barnes"]


def test_nobody_leads_a_stat_nobody_recorded(client, admin_headers, box_score, cat, user_id, db):
    set_line(db, BARNES, steals=0) # no Raptor had a steal
    pick = add_pick(db, user_id, cat["leader:steals"], player_id=BARNES)

    report = score(client, admin_headers).json()
    assert points(db, pick) == 0
    assert report["leaders"]["leader:steals"] == []


def test_a_pick_in_a_since_deactivated_category_is_still_scored(client, admin_headers, box_score, cat, user_id, db):
    pick = add_pick(db, user_id, cat["leader:steals"], player_id=BARNES)
    client.patch(f"/api/admin/pick-categories/{cat['leader:steals']}", json={"is_active": False}, headers=admin_headers)

    score(client, admin_headers)
    assert points(db, pick) == 5


# --- the report ---

def test_report_describes_the_result(client, admin_headers, box_score, cat, user_id, db):
    add_pick(db, user_id, cat["winner"], team_id=TOR)
    add_pick(db, user_id, cat["margin"], margin=7)

    report = score(client, admin_headers).json()
    assert report["scored"] is True
    assert (report["winner"], report["margin"], report["picks_scored"]) == ("TOR", 7, 2)
    assert report["leaders"]["leader:rebounds_total"] == ["Scottie Barnes"]


# --- running it more than once ---

def test_a_scored_game_is_skipped_unless_forced(client, admin_headers, box_score, cat, user_id, db):
    pick = add_pick(db, user_id, cat["leader:points"], player_id=BARNES)
    first = score(client, admin_headers).json()
    assert points(db, pick) == 2

    set_line(db, QUICKLEY, minutes="30:00", comment=None, points=40) # the nba corrects the box score
    again = score(client, admin_headers).json()
    assert again["scored"] is False
    assert again["picks_scored"] == 0
    assert again["scored_at"] == first["scored_at"]
    assert points(db, pick) == 2 # unchanged, and not doubled

    forced = score(client, admin_headers, force=True).json()
    assert forced["scored"] is True
    assert points(db, pick) == 0 # replaced: Quickley leads now


def test_reweighting_after_scoring_leaves_awarded_points_alone(client, admin_headers, box_score, cat, user_id, db):
    pick = add_pick(db, user_id, cat["leader:steals"], player_id=BARNES)
    score(client, admin_headers)
    client.patch(f"/api/admin/pick-categories/{cat['leader:steals']}", json={"points": 9}, headers=admin_headers)

    assert points(db, pick) == 5


def test_scoring_marks_the_game(client, admin_headers, box_score, cat, db):
    score(client, admin_headers)
    db.expire_all()
    assert db.get(models.Game, GAME).scored_at is not None


# --- refusals ---

def test_a_game_that_isnt_final_cannot_be_scored(client, admin_headers, box_score):
    response = score(client, admin_headers, game="0022600003") # scheduled
    assert response.status_code == 409
    assert response.json()["detail"] == "Only a final game can be scored"


def test_a_game_without_a_box_score_cannot_be_scored(client, admin_headers, box_score):
    response = score(client, admin_headers, game="0022600002") # final, but the fixture has no box score for it
    assert response.status_code == 409
    assert response.json()["detail"] == "No box score for this game yet"


def test_missing_game_is_404(client, admin_headers, box_score):
    assert score(client, admin_headers, game="0000000000").status_code == 404


def test_scoring_is_admin_only(client, user_headers, box_score):
    assert score(client, user_headers).status_code == 403
    assert score(client, {}).status_code == 401
