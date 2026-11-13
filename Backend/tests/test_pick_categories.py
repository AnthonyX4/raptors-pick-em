import asyncio

import pytest

import models
from conftest import TestAsyncSession
from routers.pick_categories import DEFAULT_CATEGORIES, ensure_default_categories


def public(client) -> list[dict]:
    response = client.get("/api/pick-categories")
    assert response.status_code == 200
    return response.json()


def by_key(client, headers) -> dict:
    return {c["key"]: c for c in client.get("/api/admin/pick-categories", headers=headers).json()}


# --- the defaults ---

def test_the_six_defaults_exist_in_form_order(client):
    categories = public(client)
    assert [c["key"] for c in categories] == [
        "winner", "margin", "leader:points", "leader:rebounds_total", "leader:assists", "leader:steals",
    ]
    assert [c["name"] for c in categories][:3] == ["Winner", "Margin of victory", "Raptors' top scorer"]


def test_only_the_winner_is_required(client):
    assert [c["key"] for c in public(client) if c["is_required"]] == ["winner"]


def test_harder_categories_are_worth_more(client):
    points = {c["key"]: c["points"] for c in public(client)}
    assert points["winner"] < points["leader:points"] < points["leader:steals"]


def test_ensuring_defaults_again_never_overwrites_an_admin_edit(client, admin_headers, db):
    winner = by_key(client, admin_headers)["winner"]
    client.patch(f"/api/admin/pick-categories/{winner['pick_category_id']}", json={"points": 7}, headers=admin_headers)

    async def run():
        async with TestAsyncSession() as session:
            await ensure_default_categories(session)
    asyncio.run(run())

    assert by_key(client, admin_headers)["winner"]["points"] == 7
    assert len(by_key(client, admin_headers)) == len(DEFAULT_CATEGORIES) # and nothing was duplicated


# --- admin: create ---

def test_admin_adds_a_stat_leader(client, admin_headers):
    response = client.post("/api/admin/pick-categories", headers=admin_headers, json={
        "kind": "stat_leader", "stat": "blocks", "name": "Raptors' blocks leader", "points": 4, "sort_order": 7,
    })
    assert response.status_code == 201
    created = response.json()
    assert created["key"] == "leader:blocks" # derived by the server, not sent
    assert public(client)[-1]["key"] == "leader:blocks"


def test_a_second_category_for_the_same_question_is_409(client, admin_headers):
    response = client.post("/api/admin/pick-categories", headers=admin_headers, json={
        "kind": "stat_leader", "stat": "points", "name": "Scorer again", "points": 2,
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "A leader:points category already exists"


def test_a_second_winner_category_is_409(client, admin_headers):
    response = client.post("/api/admin/pick-categories", headers=admin_headers, json={
        "kind": "winner", "name": "Winner 2", "points": 1,
    })
    assert response.status_code == 409


def test_a_stat_leader_needs_a_stat(client, admin_headers):
    response = client.post("/api/admin/pick-categories", headers=admin_headers, json={
        "kind": "stat_leader", "name": "Leader of what", "points": 2,
    })
    assert response.status_code == 400


def test_a_winner_category_takes_no_stat(client, admin_headers):
    response = client.post("/api/admin/pick-categories", headers=admin_headers, json={
        "kind": "winner", "stat": "points", "name": "Odd", "points": 1,
    })
    assert response.status_code == 400


@pytest.mark.parametrize("body", [
    {"kind": "stat_leader", "stat": "dunks", "name": "x", "points": 1}, # not a stat scoring can read
    {"kind": "quarter_winner", "name": "x", "points": 1},
    {"kind": "stat_leader", "stat": "blocks", "name": "x", "points": 0},
    {"kind": "stat_leader", "stat": "blocks", "name": "", "points": 1},
])
def test_invalid_categories_are_422(client, admin_headers, body):
    assert client.post("/api/admin/pick-categories", headers=admin_headers, json=body).status_code == 422


# --- admin: edit and deactivate ---

def test_reweight_and_rename(client, admin_headers):
    steals = by_key(client, admin_headers)["leader:steals"]
    response = client.patch(
        f"/api/admin/pick-categories/{steals['pick_category_id']}",
        json={"points": 6, "name": "Thief of the night"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert (response.json()["points"], response.json()["name"]) == (6, "Thief of the night")


def test_kind_and_stat_cannot_be_changed(client, admin_headers):
    steals = by_key(client, admin_headers)["leader:steals"]
    response = client.patch(
        f"/api/admin/pick-categories/{steals['pick_category_id']}",
        json={"kind": "winner", "stat": "points"},
        headers=admin_headers,
    )
    assert response.status_code == 200 # unknown fields are ignored...
    assert response.json()["key"] == "leader:steals" # ...so the question is unchanged


def test_deactivated_category_leaves_the_public_list_but_not_the_admin_one(client, admin_headers):
    margin = by_key(client, admin_headers)["margin"]
    client.patch(f"/api/admin/pick-categories/{margin['pick_category_id']}", json={"is_active": False}, headers=admin_headers)

    assert "margin" not in [c["key"] for c in public(client)]
    assert by_key(client, admin_headers)["margin"]["is_active"] is False


def test_edit_missing_category_is_404(client, admin_headers):
    assert client.patch("/api/admin/pick-categories/999", json={"points": 2}, headers=admin_headers).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("get", "/api/admin/pick-categories"),
    ("post", "/api/admin/pick-categories"),
    ("patch", "/api/admin/pick-categories/1"),
])
def test_category_management_is_admin_only(client, user_headers, method, path):
    assert client.request(method, path, json={}, headers=user_headers).status_code == 403
