import pytest
from sqlalchemy import select

import models

OLD, G1, G2 = "0022500001", "0022600001", "0022600002" # one 2025-26 game, two 2026-27 games (games fixture)


@pytest.fixture
def standings(client, db, games):
    """Scored picks for six users, written straight to the database: the leaderboard only adds them up.

    2026-27: alice 6, bob 4, carol 4, dave 1, frank 0. dave also has 10 from 2025-26.
    erin has a pick that hasn't been scored and shouldn't appear anywhere.
    """
    cat = {c.key: c.pick_category_id for c in db.execute(select(models.PickCategory)).scalars()}
    users = {}
    for name in ["alice", "bob", "carol", "dave", "erin", "frank"]:
        user = models.User(username=name, email=f"{name}@example.com", password_hash="x")
        db.add(user)
        db.flush()
        users[name] = user.user_id

    for name, game, key, points in [
        ("alice", G1, "winner", 1), ("alice", G1, "leader:steals", 5),
        ("bob", G1, "winner", 1), ("bob", G1, "margin", 3),
        ("carol", G2, "winner", 1), ("carol", G2, "margin", 3),
        ("dave", G2, "winner", 1), ("dave", OLD, "winner", 1), ("dave", OLD, "leader:points", 9),
        ("erin", G2, "winner", None),
        ("frank", G1, "winner", 0), ("frank", G1, "margin", 0),
    ]:
        db.add(models.Pick(user_id=users[name], game_id=game, pick_category_id=cat[key], points_awarded=points))
    db.commit()


def board(client, path="/api/leaderboard", **params):
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def rows(page):
    return [(e["rank"], e["user"]["username"], e["total_points"]) for e in page["entries"]]


def test_season_standings_with_shared_ranks(client, standings):
    page = board(client, season="2026-27")
    assert rows(page) == [
        (1, "alice", 6), (2, "bob", 4), (2, "carol", 4), (4, "dave", 1), (5, "frank", 0),
    ]
    assert page["total"] == 5


def test_all_time_standings_include_every_season(client, standings):
    assert rows(board(client))[:2] == [(1, "dave", 11), (2, "alice", 6)]


def test_an_unscored_pick_counts_for_nothing_and_shows_no_one(client, standings):
    assert "erin" not in [e["user"]["username"] for e in board(client)["entries"]]


def test_a_scored_zero_still_puts_you_on_the_board(client, standings):
    frank = next(e for e in board(client, season="2026-27")["entries"] if e["user"]["username"] == "frank")
    assert (frank["total_points"], frank["picks_scored"], frank["correct_picks"]) == (0, 2, 0)


def test_entry_counts(client, standings):
    entries = {e["user"]["username"]: e for e in board(client)["entries"]}
    assert (entries["alice"]["picks_scored"], entries["alice"]["correct_picks"], entries["alice"]["games_played"]) == (2, 2, 1)
    assert entries["dave"]["games_played"] == 2


def test_ranks_stay_true_on_later_pages(client, standings):
    # rank is computed over the whole board before paging, so page two doesn't restart at 1
    page = board(client, season="2026-27", skip=2, limit=2)
    assert rows(page) == [(2, "carol", 4), (4, "dave", 1)]
    assert page["has_more"] is True


def test_one_games_standings(client, standings):
    page = board(client, f"/api/leaderboard/games/{G1}")
    assert rows(page) == [(1, "alice", 6), (2, "bob", 4), (3, "frank", 0)]


def test_an_unscored_games_standings_are_empty(client, standings):
    page = board(client, "/api/leaderboard/games/0022600003")
    assert page["entries"] == []
    assert page["total"] == 0


def test_an_unknown_game_is_404(client, standings):
    assert client.get("/api/leaderboard/games/0000000000").status_code == 404


def test_the_board_shows_public_profiles_only(client, standings):
    entry = board(client)["entries"][0]
    assert "email" not in entry["user"]
    assert entry["user"]["image_path"] == "/static/profile_pics/default.jpg"


def test_an_empty_board(client, games):
    page = board(client)
    assert (page["entries"], page["total"], page["has_more"]) == ([], 0, False)
