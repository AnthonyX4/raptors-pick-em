from datetime import datetime, timedelta, UTC

import pytest
from sqlalchemy import select

import models
from conftest import register_and_login
from test_messages import GAME, TIPOFF, clock, game, page, post, posted # noqa: F401 (fixtures)

START = TIPOFF - timedelta(hours=2) # where the clock fixture starts


def me(client, headers) -> int:
    return client.get("/api/users/me", headers=headers).json()["user_id"]


def mute(client, admin_headers, user_id, hours=24, reason="spam"):
    return client.put(f"/api/admin/users/{user_id}/mute", json={"hours": hours, "reason": reason}, headers=admin_headers)


# --- muting (decided: timed, the admin picks how long) ---

def test_a_muted_user_can_read_but_not_post(client, user_headers, admin_headers, game):
    posted(client, user_headers, "before the mute")
    response = mute(client, admin_headers, me(client, user_headers))
    assert response.status_code == 200
    assert response.json()["muted_until"] == "2027-01-10T22:30:00Z" # 24h from the clock
    assert response.json()["user"]["username"] == "customer"

    refused = post(client, user_headers)
    assert refused.status_code == 403
    assert refused.json()["detail"] == "You're muted until 2027-01-10T22:30:00+00:00"
    assert [m["body"] for m in page(client)["messages"]] == ["before the mute"]


def test_a_muted_user_cannot_edit_either(client, user_headers, admin_headers, game):
    message = posted(client, user_headers)
    mute(client, admin_headers, me(client, user_headers))
    response = client.patch(f"/api/messages/{message['message_id']}", json={"body": "sneaky"}, headers=user_headers)
    assert response.status_code == 403


def test_a_mute_only_affects_its_user(client, user_headers, admin_headers, game):
    mute(client, admin_headers, me(client, user_headers))
    assert post(client, register_and_login(client, "other@example.com")).status_code == 201


def test_a_mute_runs_out_by_itself(client, user_headers, admin_headers, game, clock):
    mute(client, admin_headers, me(client, user_headers), hours=1)
    clock(START + timedelta(hours=1))
    assert post(client, user_headers).status_code == 201


def test_unmute_early(client, user_headers, admin_headers, game):
    user_id = me(client, user_headers)
    mute(client, admin_headers, user_id)
    assert client.delete(f"/api/admin/users/{user_id}/mute", headers=admin_headers).status_code == 204
    assert post(client, user_headers).status_code == 201
    assert client.delete(f"/api/admin/users/{user_id}/mute", headers=admin_headers).status_code == 204 # nothing left to lift


def test_muting_again_replaces_the_old_mute(client, user_headers, admin_headers, game, clock):
    user_id = me(client, user_headers)
    mute(client, admin_headers, user_id, hours=24)
    mute(client, admin_headers, user_id, hours=1) # an admin correcting a mistake
    clock(START + timedelta(hours=1))
    assert post(client, user_headers).status_code == 201


def test_admins_cant_be_muted(client, admin_headers):
    response = mute(client, admin_headers, me(client, admin_headers))
    assert response.status_code == 403
    assert response.json()["detail"] == "Admins can't be muted"


def test_muting_a_missing_user_is_404(client, admin_headers):
    assert mute(client, admin_headers, 999).status_code == 404


@pytest.mark.parametrize("hours", [0, 24 * 30 + 1])
def test_mute_length_is_limited(client, user_headers, admin_headers, hours):
    assert mute(client, admin_headers, me(client, user_headers), hours=hours).status_code == 422


def test_the_mute_list_shows_only_mutes_in_force(client, user_headers, admin_headers, game, clock):
    short = me(client, user_headers)
    long = me(client, register_and_login(client, "troll@example.com"))
    mute(client, admin_headers, short, hours=1)
    mute(client, admin_headers, long, hours=48)

    listed = client.get("/api/admin/mutes", headers=admin_headers).json()
    assert [m["user"]["username"] for m in listed["mutes"]] == ["customer", "troll"] # soonest to expire first

    clock(START + timedelta(hours=2))
    listed = client.get("/api/admin/mutes", headers=admin_headers).json()
    assert ([m["user"]["username"] for m in listed["mutes"]], listed["total"]) == (["troll"], 1)


# --- admin deletes ---

def test_an_admin_deletes_anyones_message(client, user_headers, admin_headers, game):
    message = posted(client, user_headers)
    assert client.delete(f"/api/admin/messages/{message['message_id']}", headers=admin_headers).status_code == 204
    assert page(client)["messages"] == []


def test_admin_delete_of_a_missing_message_is_404(client, admin_headers):
    assert client.delete("/api/admin/messages/999", headers=admin_headers).status_code == 404


@pytest.mark.parametrize("method,path", [
    ("delete", "/api/admin/messages/1"),
    ("put", "/api/admin/users/1/mute"),
    ("delete", "/api/admin/users/1/mute"),
    ("get", "/api/admin/mutes"),
])
def test_moderation_is_admin_only(client, user_headers, method, path):
    assert client.request(method, path, json={"hours": 1}, headers=user_headers).status_code == 403


# --- deleted accounts (decided: messages stay, shown as "[deleted]") ---

def test_a_deleted_account_leaves_its_messages_authorless(client, user_headers, admin_headers, game, db):
    fan = register_and_login(client, "fan@example.com")
    leaving = me(client, user_headers)
    mine = posted(client, user_headers, "I said something")
    theirs = posted(client, fan, "a reply")
    client.put(f"/api/messages/{theirs['message_id']}/like", headers=user_headers)
    mute(client, admin_headers, leaving)

    assert client.delete(f"/api/users/{leaving}", headers=user_headers).status_code == 204

    messages = page(client)["messages"]
    assert [(m["body"], m["author"]) for m in messages][0] == ("I said something", None)
    assert messages[1]["author"]["username"] == "fan"
    assert messages[1]["like_count"] == 0 # their like went with them
    assert db.execute(select(models.Mute)).scalars().all() == [] # and so did their mute
