from datetime import datetime, timedelta, UTC

import pytest
from sqlalchemy import select

import models
from conftest import BOS, TOR, register_and_login
from routers import messages as chat

GAME = "0022600099"
OTHER_GAME = "0022600098"
TIPOFF = datetime(2027, 1, 10, 0, 30, tzinfo=UTC)


@pytest.fixture
def clock(monkeypatch):
    """Sets what time the chat thinks it is (mutes included). Starts two hours before tipoff."""
    now = {"value": TIPOFF - timedelta(hours=2)}
    monkeypatch.setattr(chat, "utcnow", lambda: now["value"])

    def set_time(value: datetime):
        now["value"] = value
    return set_time


@pytest.fixture
def game(db, teams, clock):
    db.add_all([
        models.Game(game_id=GAME, season="2026-27", tipoff_utc=TIPOFF, status="scheduled",
                    home_team_id=TOR, away_team_id=BOS),
        models.Game(game_id=OTHER_GAME, season="2026-27", tipoff_utc=TIPOFF, status="scheduled",
                    home_team_id=BOS, away_team_id=TOR),
    ])
    db.commit()
    return GAME


def post(client, headers, body="Let's go Raptors", game_id=GAME):
    return client.post(f"/api/games/{game_id}/messages", json={"body": body}, headers=headers)


def posted(client, headers, body="Let's go Raptors") -> dict:
    response = post(client, headers, body)
    assert response.status_code == 201, response.text
    return response.json()


def page(client, headers=None, game_id=GAME, **params) -> dict:
    response = client.get(f"/api/games/{game_id}/messages", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def bodies(result) -> list[str]:
    return [m["body"] for m in result["messages"]]


def set_game(db, **fields):
    game = db.get(models.Game, GAME)
    for name, value in fields.items():
        setattr(game, name, value)
    db.commit()


# --- when the room is open (decided: game day, 24h before tipoff until 3h after the game ends) ---

def test_the_room_opens_24_hours_before_tipoff(client, user_headers, game, clock):
    clock(TIPOFF - timedelta(hours=24, seconds=1))
    assert post(client, user_headers).status_code == 409
    assert page(client)["room_open"] is False

    clock(TIPOFF - timedelta(hours=24))
    assert post(client, user_headers).status_code == 201
    assert page(client)["opens_at"] == "2027-01-09T00:30:00Z"


def test_the_room_stays_open_through_the_game(client, user_headers, game, db, clock):
    set_game(db, status="live")
    clock(TIPOFF + timedelta(hours=2))
    assert post(client, user_headers).status_code == 201


def test_the_room_closes_3_hours_after_the_game_goes_final(client, user_headers, game, db, clock):
    final_at = TIPOFF + timedelta(hours=2, minutes=30)
    set_game(db, status="final", final_at=final_at)

    clock(final_at + timedelta(hours=3) - timedelta(seconds=1))
    assert post(client, user_headers).status_code == 201
    clock(final_at + timedelta(hours=3))
    response = post(client, user_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "This game's chat is closed"
    assert page(client)["closes_at"] == "2027-01-10T06:00:00Z"


def test_a_game_that_was_over_before_we_saw_it_has_a_closed_room(client, user_headers, game, db):
    set_game(db, status="final", final_at=None) # seeded, or caught up by the schedule refresh
    assert post(client, user_headers).status_code == 409


def test_a_postponed_games_room_is_closed(client, user_headers, game, db):
    set_game(db, status="postponed")
    assert post(client, user_headers).status_code == 409


def test_a_closed_room_can_still_be_read(client, user_headers, game, db, clock):
    posted(client, user_headers, "before it closed")
    set_game(db, status="final", final_at=TIPOFF)
    clock(TIPOFF + timedelta(days=30))
    result = page(client)
    assert bodies(result) == ["before it closed"]
    assert result["room_open"] is False


def test_unknown_game_is_404(client, user_headers, game):
    assert post(client, user_headers, game_id="0000000000").status_code == 404
    assert client.get("/api/games/0000000000/messages").status_code == 404


# --- posting ---

def test_a_message_carries_its_author(client, user_headers, game):
    message = posted(client, user_headers)
    assert message["author"]["username"] == "customer"
    assert "email" not in message["author"]
    assert (message["like_count"], message["liked_by_me"], message["edited_at"]) == (0, False, None)


def test_posting_needs_a_login_but_reading_doesnt(client, user_headers, game):
    posted(client, user_headers)
    assert post(client, {}).status_code == 401
    assert bodies(page(client)) == ["Let's go Raptors"]


def test_whitespace_is_trimmed(client, user_headers, game):
    assert posted(client, user_headers, "   we up   ")["body"] == "we up"


@pytest.mark.parametrize("body", ["", "    ", "x" * 501])
def test_empty_or_too_long_is_422(client, user_headers, game, body):
    assert post(client, user_headers, body).status_code == 422


def test_500_characters_is_fine(client, user_headers, game):
    assert post(client, user_headers, "x" * 500).status_code == 201


# --- reading: cursor pages ---

@pytest.fixture
def five(client, user_headers, game) -> list[int]:
    return [posted(client, user_headers, f"m{i}")["message_id"] for i in range(1, 6)]


def test_the_first_page_is_the_newest_read_oldest_first(client, five):
    result = page(client, limit=2)
    assert bodies(result) == ["m4", "m5"]
    assert (result["has_older"], result["has_newer"]) == (True, False)


def test_scrolling_back_with_before(client, five):
    result = page(client, limit=2, before=five[3]) # older than m4
    assert bodies(result) == ["m2", "m3"]
    assert (result["has_older"], result["has_newer"]) == (True, True)
    assert bodies(page(client, limit=2, before=five[1])) == ["m1"]


def test_polling_for_new_messages_with_after(client, user_headers, five):
    newest = page(client)["messages"][-1]["message_id"]
    assert page(client, after=newest)["messages"] == [] # nothing new yet

    posted(client, user_headers, "m6")
    result = page(client, after=newest)
    assert bodies(result) == ["m6"]
    assert result["has_newer"] is False


def test_after_pages_forward_when_many_arrived(client, five):
    result = page(client, after=five[0], limit=2)
    assert bodies(result) == ["m2", "m3"]
    assert result["has_newer"] is True


def test_an_empty_poll_says_nothing_newer(client, five):
    result = page(client, after=five[-1])
    assert (result["messages"], result["has_newer"], result["has_older"]) == ([], False, True)


def test_before_and_after_together_is_400(client, five):
    assert client.get(f"/api/games/{GAME}/messages", params={"before": 3, "after": 1}).status_code == 400


def test_rooms_are_separate(client, user_headers, game):
    posted(client, user_headers, "in this room")
    post(client, user_headers, "in the other room", game_id=OTHER_GAME)
    assert bodies(page(client)) == ["in this room"]


def test_ids_only_grow_even_after_deleting_the_newest(client, user_headers, game):
    # what makes ?after= safe: without AUTOINCREMENT the next message would reuse the deleted id
    first = posted(client, user_headers, "a")
    newest = posted(client, user_headers, "b")
    client.delete(f"/api/messages/{newest['message_id']}", headers=user_headers)
    assert posted(client, user_headers, "c")["message_id"] > newest["message_id"]


# --- editing (decided: 5 minutes) and deleting (any time) ---

def test_edit_within_5_minutes(client, user_headers, game, clock):
    message = posted(client, user_headers, "Barnes for MVP")
    clock(TIPOFF - timedelta(hours=2) + timedelta(minutes=5))
    response = client.patch(f"/api/messages/{message['message_id']}", json={"body": "Barnes for DPOY"}, headers=user_headers)
    assert response.status_code == 200
    assert response.json()["body"] == "Barnes for DPOY"
    assert response.json()["edited_at"] is not None


def test_message_says_until_when_it_can_be_edited(client, user_headers, game):
    # the frontend shows the edit button from this rather than redoing the 5 minute rule
    message = posted(client, user_headers)
    created = datetime.fromisoformat(message["created_at"])
    assert datetime.fromisoformat(message["editable_until"]) == created + timedelta(minutes=5)
    assert page(client)["messages"][0]["editable_until"] == message["editable_until"]


def test_no_edits_after_5_minutes(client, user_headers, game, clock):
    message = posted(client, user_headers)
    clock(TIPOFF - timedelta(hours=2) + timedelta(minutes=5, seconds=1))
    response = client.patch(f"/api/messages/{message['message_id']}", json={"body": "changed"}, headers=user_headers)
    assert response.status_code == 409
    assert response.json()["detail"] == "Messages can only be edited for 5 minutes"


def test_only_the_author_edits_or_deletes(client, user_headers, game):
    message = posted(client, user_headers)
    other = register_and_login(client, "other@example.com")
    assert client.patch(f"/api/messages/{message['message_id']}", json={"body": "x"}, headers=other).status_code == 403
    assert client.delete(f"/api/messages/{message['message_id']}", headers=other).status_code == 403


def test_delete_your_message_even_after_the_room_closes(client, user_headers, game, db, clock):
    message = posted(client, user_headers)
    set_game(db, status="final", final_at=TIPOFF)
    clock(TIPOFF + timedelta(days=1))
    assert client.delete(f"/api/messages/{message['message_id']}", headers=user_headers).status_code == 204
    assert page(client)["messages"] == []


def test_missing_message_is_404(client, user_headers, game):
    assert client.patch("/api/messages/999", json={"body": "x"}, headers=user_headers).status_code == 404
    assert client.delete("/api/messages/999", headers=user_headers).status_code == 404


# --- likes ---

def test_like_and_unlike(client, user_headers, game):
    message = posted(client, user_headers)
    fan = register_and_login(client, "fan@example.com")
    url = f"/api/messages/{message['message_id']}/like"

    liked = client.put(url, headers=fan).json()
    assert (liked["like_count"], liked["liked_by_me"]) == (1, True)
    assert client.put(url, headers=fan).json()["like_count"] == 1 # liking twice is liking once

    assert page(client, headers=fan)["messages"][0]["liked_by_me"] is True
    assert page(client, headers=user_headers)["messages"][0]["liked_by_me"] is False
    assert page(client)["messages"][0]["like_count"] == 1 # anonymous readers see counts too

    assert client.delete(url, headers=fan).json()["like_count"] == 0
    assert client.delete(url, headers=fan).status_code == 200 # unliking twice is fine too


def test_likes_count_everyone(client, user_headers, game):
    message = posted(client, user_headers)
    for email in ("a@example.com", "b@example.com", "c@example.com"):
        client.put(f"/api/messages/{message['message_id']}/like", headers=register_and_login(client, email))
    assert page(client)["messages"][0]["like_count"] == 3


def test_no_likes_in_a_closed_room(client, user_headers, game, db, clock):
    message = posted(client, user_headers)
    set_game(db, status="final", final_at=TIPOFF)
    clock(TIPOFF + timedelta(days=1))
    assert client.put(f"/api/messages/{message['message_id']}/like", headers=user_headers).status_code == 409


def test_deleting_a_message_deletes_its_likes(client, user_headers, game, db):
    message = posted(client, user_headers)
    client.put(f"/api/messages/{message['message_id']}/like", headers=user_headers)
    client.delete(f"/api/messages/{message['message_id']}", headers=user_headers)
    assert db.execute(select(models.MessageLike)).scalars().all() == []


def test_a_stale_token_is_401_even_on_a_public_page(client, game):
    response = client.get(f"/api/games/{GAME}/messages", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
