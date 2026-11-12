def list_players(client, **params) -> dict:
    response = client.get("/api/players", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_players_are_listed_by_name(client, players):
    page = list_players(client)
    assert [p["full_name"] for p in page["players"]] == [
        "Free Agent", "Immanuel Quickley", "Jayson Tatum", "Scottie Barnes",
    ]
    assert page["total"] == 4


def test_player_carries_their_team(client, players):
    barnes = next(p for p in list_players(client)["players"] if p["full_name"] == "Scottie Barnes")
    assert barnes["team"]["tricode"] == "TOR"
    assert barnes["jersey_number"] == "4"
    assert barnes["position"] == "F"


def test_a_player_on_no_roster_has_no_team(client, players):
    free_agent = next(p for p in list_players(client)["players"] if p["full_name"] == "Free Agent")
    assert free_agent["team"] is None


def test_filter_by_team(client, players):
    page = list_players(client, team="TOR")
    assert [p["full_name"] for p in page["players"]] == ["Immanuel Quickley", "Scottie Barnes"]
    assert page["total"] == 2


def test_search_matches_anywhere_ignoring_case(client, players):
    assert [p["full_name"] for p in list_players(client, search="quick")["players"]] == ["Immanuel Quickley"]
    assert [p["full_name"] for p in list_players(client, search="BARNES")["players"]] == ["Scottie Barnes"]


def test_search_and_team_combine(client, players):
    # the pick form's case: narrowing one roster as someone types
    assert list_players(client, team="TOR", search="a")["total"] == 2
    assert list_players(client, team="BOS", search="a")["total"] == 1


def test_search_with_no_matches_is_an_empty_page(client, players):
    page = list_players(client, search="nobody")
    assert page["players"] == []
    assert page["total"] == 0
    assert page["has_more"] is False


def test_unknown_team_is_400(client, players):
    response = client.get("/api/players", params={"team": "XYZ"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown team tricode: XYZ"


def test_pagination(client, players):
    page = list_players(client, limit=2)
    assert [p["full_name"] for p in page["players"]] == ["Free Agent", "Immanuel Quickley"]
    assert page["total"] == 4
    assert page["has_more"] is True


def test_get_one_player(client, players):
    response = client.get("/api/players/1")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Scottie Barnes"


def test_missing_player_is_404(client, players):
    assert client.get("/api/players/999").status_code == 404
