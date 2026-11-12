import pytest

from config import settings


def list_games(client, **params) -> dict:
    response = client.get("/api/games", params=params)
    assert response.status_code == 200, response.text
    return response.json()


# --- listing ---

def test_games_are_listed_oldest_first(client, games):
    page = list_games(client)
    assert [game["game_id"] for game in page["games"]] == games # the fixture is already in tipoff order
    assert page["total"] == 4
    assert page["has_more"] is False


def test_game_carries_both_teams_and_the_score(client, games):
    game = next(g for g in list_games(client)["games"] if g["game_id"] == "0022600001")
    assert game["home_team"]["tricode"] == "TOR"
    assert game["away_team"]["full_name"] == "Boston Celtics"
    assert (game["home_score"], game["away_score"]) == (115, 108)
    assert game["status"] == "final"
    assert game["tipoff_utc"] == "2026-10-22T23:30:00Z" # the Z matters: without it a browser reads the time as local


def test_a_scheduled_game_has_no_score_yet(client, games):
    game = next(g for g in list_games(client)["games"] if g["status"] == "scheduled")
    assert game["home_score"] is None
    assert game["away_score"] is None
    assert game["period"] is None


# --- filters ---

def test_filter_by_season(client, games):
    page = list_games(client, season="2026-27")
    assert page["total"] == 3
    assert all(game["season"] == "2026-27" for game in page["games"])


def test_filter_by_status_puts_the_next_game_first(client, games):
    page = list_games(client, status="scheduled")
    assert [game["game_id"] for game in page["games"]] == ["0022600003"]


def test_filter_by_opponent_matches_either_side(client, games):
    # MIA is the away team in one of these games and the home team in the other
    assert [g["game_id"] for g in list_games(client, opponent="MIA")["games"]] == ["0022500001", "0022600002"]
    assert [g["game_id"] for g in list_games(client, opponent="BOS")["games"]] == ["0022600001", "0022600003"]


def test_opponent_filter_ignores_case(client, games):
    assert list_games(client, opponent="bos")["total"] == 2


def test_filters_combine(client, games):
    page = list_games(client, season="2026-27", opponent="BOS", status="final")
    assert [game["game_id"] for game in page["games"]] == ["0022600001"]


def test_unknown_opponent_is_400_not_an_empty_page(client, games):
    response = client.get("/api/games", params={"opponent": "XYZ"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown team tricode: XYZ"


def test_unknown_status_value_is_422(client, games):
    assert client.get("/api/games", params={"status": "rained-off"}).status_code == 422


# --- pagination ---

def test_pages_cover_every_game_once(client, games):
    seen, skip = [], 0
    while True:
        page = list_games(client, skip=skip, limit=2)
        seen += [game["game_id"] for game in page["games"]]
        if not page["has_more"]:
            break
        skip += 2
    assert seen == games


def test_total_counts_matching_games_not_just_the_page(client, games):
    page = list_games(client, season="2026-27", limit=1)
    assert page["total"] == 3
    assert len(page["games"]) == 1
    assert page["has_more"] is True


def test_default_limit_comes_from_settings(client, games):
    assert list_games(client)["limit"] == settings.games_per_page


@pytest.mark.parametrize("params", [{"skip": -1}, {"limit": 0}, {"limit": settings.max_page_size + 1}])
def test_out_of_range_params_are_422(client, games, params):
    assert client.get("/api/games", params=params).status_code == 422


# --- detail ---

def test_game_detail_returns_the_box_score_highest_scorer_first(client, box_score):
    response = client.get("/api/games/0022600001")
    assert response.status_code == 200
    detail = response.json()

    assert [stat["player"]["full_name"] for stat in detail["player_stats"]] == [
        "Jayson Tatum", "Scottie Barnes", "Immanuel Quickley",
    ]
    barnes = detail["player_stats"][1]
    assert (barnes["points"], barnes["rebounds_total"], barnes["assists"]) == (22, 9, 5)
    assert barnes["player"]["team"]["tricode"] == "TOR"


def test_a_player_who_did_not_appear_still_has_a_line(client, box_score):
    detail = client.get("/api/games/0022600001").json()
    dnp = detail["player_stats"][-1]
    assert dnp["minutes"] is None
    assert dnp["comment"] == "DNP - Coach's Decision"
    assert dnp["points"] == 0


def test_a_game_with_no_box_score_yet_has_an_empty_list(client, games):
    detail = client.get("/api/games/0022600003").json()
    assert detail["player_stats"] == []


def test_missing_game_is_404(client, games):
    assert client.get("/api/games/9999999999").status_code == 404


def test_games_need_no_token(client, games):
    assert client.get("/api/games").status_code == 200
    assert client.get("/api/games/0022600001").status_code == 200
