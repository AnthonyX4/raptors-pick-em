import asyncio
from datetime import datetime, timedelta, UTC

import pytest
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

import models
from chat_hub import ChatHub, hub
from conftest import BOS, TOR, register_and_login
from routers import messages as chat

GAME = "0022600099"
OTHER_GAME = "0022600098"
TIPOFF = datetime(2027, 1, 10, 0, 30, tzinfo=UTC)


class Ping(BaseModel):
    """Stands in for a chat event: the real ones arrive with the broadcasts from the chat routes (step 17.2)."""
    type: str = "ping"
    n: int = 1


@pytest.fixture(autouse=True)
def empty_hub():
    # the hub is one object for the whole test run, so no test may leave a socket behind for the next one
    yield
    hub.rooms.clear()


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    # two hours before tipoff, so the room is open. the same clock the chat routes and mutes read
    monkeypatch.setattr(chat, "utcnow", lambda: TIPOFF - timedelta(hours=2))


@pytest.fixture
def game(db, teams):
    db.add_all([
        models.Game(game_id=GAME, season="2026-27", tipoff_utc=TIPOFF, status="scheduled",
                    home_team_id=TOR, away_team_id=BOS),
        models.Game(game_id=OTHER_GAME, season="2026-27", tipoff_utc=TIPOFF, status="scheduled",
                    home_team_id=BOS, away_team_id=TOR),
    ])
    db.commit()
    return GAME


def broadcast(client, game_id: str, event: BaseModel) -> None:
    # the hub is async and the test is not: run it on the event loop the TestClient keeps for the app
    client.portal.call(hub.broadcast, game_id, event)


# --- connecting ---

def test_a_socket_joins_its_games_room_and_leaves_it_on_disconnect(client, game):
    with client.websocket_connect(f"/api/games/{GAME}/ws"):
        assert len(hub.rooms[GAME]) == 1
    assert GAME not in hub.rooms # the empty room is gone too, not left as an empty set


def test_an_unknown_game_is_refused(client, game):
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/api/games/nope/ws"):
            pass
    assert refused.value.code == 1008
    assert hub.rooms == {}


def test_a_closed_room_can_still_be_listened_to(client, db, game):
    # reading is public at any time, and the room can reopen (a postponed game gets its new date)
    long_ago = datetime(2026, 1, 1, tzinfo=UTC)
    game_row = db.get(models.Game, GAME)
    game_row.status, game_row.final_at = "final", long_ago
    db.commit()

    with client.websocket_connect(f"/api/games/{GAME}/ws"):
        assert len(hub.rooms[GAME]) == 1


# --- delivering ---

def test_a_broadcast_reaches_everyone_in_that_room_and_no_one_else(client, game):
    with (
        client.websocket_connect(f"/api/games/{GAME}/ws") as first,
        client.websocket_connect(f"/api/games/{GAME}/ws") as second,
        client.websocket_connect(f"/api/games/{OTHER_GAME}/ws") as elsewhere,
    ):
        broadcast(client, GAME, Ping(n=7))
        assert first.receive_json() == {"type": "ping", "n": 7}
        assert second.receive_json() == {"type": "ping", "n": 7}

        # nothing was queued for the other room: the next thing it hears is its own broadcast
        broadcast(client, OTHER_GAME, Ping(n=8))
        assert elsewhere.receive_json() == {"type": "ping", "n": 8}


def test_a_broadcast_to_an_empty_room_does_nothing(client, game):
    broadcast(client, GAME, Ping())


def test_what_a_client_sends_is_ignored(client, game):
    with client.websocket_connect(f"/api/games/{GAME}/ws") as socket:
        socket.send_text("hello?")
        socket.send_text("anyone there?")
        broadcast(client, GAME, Ping(n=3))
        assert socket.receive_json() == {"type": "ping", "n": 3} # still open, still listening


# --- a socket that has gone ---

class FakeSocket:
    """Just enough of a WebSocket for the hub: accepts, and either receives or fails on send."""
    def __init__(self, broken: bool = False) -> None:
        self.broken = broken
        self.received: list[str] = []

    async def accept(self) -> None:
        pass

    async def send_text(self, text: str) -> None:
        if self.broken:
            raise RuntimeError("the tab closed mid-broadcast")
        self.received.append(text)


def test_a_socket_that_fails_on_send_is_dropped_and_the_others_still_get_the_event():
    async def go():
        room = ChatHub()
        gone, there = FakeSocket(broken=True), FakeSocket()
        await room.connect(GAME, gone)
        await room.connect(GAME, there)

        await room.broadcast(GAME, Ping(n=5)) # must not raise
        assert room.rooms[GAME] == {there}
        assert there.received == ['{"type":"ping","n":5}']
    asyncio.run(go())


# --- the chat routes broadcast their writes (step 17.2) ---

def url(game_id: str = GAME) -> str:
    return f"/api/games/{game_id}/ws"


def post(client, headers, body="Let's go Raptors", game_id=GAME):
    return client.post(f"/api/games/{game_id}/messages", json={"body": body}, headers=headers)


def test_posting_sends_message_created_with_the_message(client, game, user_headers):
    with client.websocket_connect(url()) as socket:
        posted = post(client, user_headers).json()
        event = socket.receive_json()

    assert event["type"] == "message.created"
    assert event["message"] == posted # the same ChatMessageResponse the poster got back
    assert event["message"]["liked_by_me"] is False # nothing per-reader in an event


def test_editing_sends_message_edited(client, game, user_headers):
    posted = post(client, user_headers).json()
    with client.websocket_connect(url()) as socket:
        edited = client.patch(f"/api/messages/{posted['message_id']}", json={"body": "Fixed"}, headers=user_headers).json()
        event = socket.receive_json()

    assert event == {
        "type": "message.edited", "message_id": posted["message_id"], "body": "Fixed", "edited_at": edited["edited_at"],
    }


def test_deleting_your_own_message_sends_message_deleted(client, game, user_headers):
    message_id = post(client, user_headers).json()["message_id"]
    with client.websocket_connect(url()) as socket:
        assert client.delete(f"/api/messages/{message_id}", headers=user_headers).status_code == 204
        assert socket.receive_json() == {"type": "message.deleted", "message_id": message_id}


def test_an_admin_deleting_a_message_sends_message_deleted_to_its_room(client, game, user_headers, admin_headers):
    message_id = post(client, user_headers).json()["message_id"]
    with client.websocket_connect(url()) as socket, client.websocket_connect(url(OTHER_GAME)) as elsewhere:
        assert client.delete(f"/api/admin/messages/{message_id}", headers=admin_headers).status_code == 204
        assert socket.receive_json() == {"type": "message.deleted", "message_id": message_id}

        # the other game's room heard nothing: the first thing it receives is its own post
        post(client, user_headers, game_id=OTHER_GAME)
        assert elsewhere.receive_json()["type"] == "message.created"


def test_liking_and_unliking_send_the_new_total(client, game, user_headers):
    other_headers = register_and_login(client, "fan@example.com")
    message_id = post(client, user_headers).json()["message_id"]
    with client.websocket_connect(url()) as socket:
        client.put(f"/api/messages/{message_id}/like", headers=user_headers)
        assert socket.receive_json() == {"type": "message.likes", "message_id": message_id, "like_count": 1}

        client.put(f"/api/messages/{message_id}/like", headers=other_headers)
        assert socket.receive_json()["like_count"] == 2

        client.delete(f"/api/messages/{message_id}/like", headers=user_headers)
        assert socket.receive_json()["like_count"] == 1


def test_liking_twice_repeats_the_same_total(client, game, user_headers):
    message_id = post(client, user_headers).json()["message_id"]
    with client.websocket_connect(url()) as socket:
        client.put(f"/api/messages/{message_id}/like", headers=user_headers)
        client.put(f"/api/messages/{message_id}/like", headers=user_headers)
        assert socket.receive_json()["like_count"] == 1
        assert socket.receive_json()["like_count"] == 1 # absolute, so the repeat does no harm


def test_the_change_is_saved_before_anyone_hears_of_it(client, game, user_headers):
    # a tab that gets the event and then asks the api must already find the change there
    with client.websocket_connect(url()) as socket:
        post(client, user_headers)
        message_id = socket.receive_json()["message"]["message_id"]

        client.patch(f"/api/messages/{message_id}", json={"body": "Fixed"}, headers=user_headers)
        socket.receive_json()
        assert client.get(f"/api/games/{GAME}/messages").json()["messages"][0]["body"] == "Fixed"

        client.delete(f"/api/messages/{message_id}", headers=user_headers)
        socket.receive_json()
        assert client.get(f"/api/games/{GAME}/messages").json()["messages"] == []


def test_a_refused_write_sends_nothing(client, db, game, user_headers):
    other_headers = register_and_login(client, "fan@example.com")
    message_id = post(client, user_headers).json()["message_id"]
    with client.websocket_connect(url()) as socket:
        # a stranger can't edit or delete it, and nobody can post to an unknown game
        assert client.patch(f"/api/messages/{message_id}", json={"body": "Mine now"}, headers=other_headers).status_code == 403
        assert client.delete(f"/api/messages/{message_id}", headers=other_headers).status_code == 403
        assert post(client, user_headers, game_id="nope").status_code == 404

        # so the first thing this socket hears is the next successful write
        post(client, user_headers, body="Second")
        assert socket.receive_json()["message"]["body"] == "Second"


def test_a_muted_user_posting_sends_nothing(client, game, user_headers, admin_headers):
    user_id = client.get("/api/users/me", headers=user_headers).json()["user_id"]
    client.put(f"/api/admin/users/{user_id}/mute", json={"hours": 1}, headers=admin_headers)
    with client.websocket_connect(url()) as socket:
        assert post(client, user_headers).status_code == 403
        post(client, admin_headers, body="Admin speaks")
        assert socket.receive_json()["message"]["body"] == "Admin speaks"


def test_a_closed_socket_in_the_room_does_not_fail_the_post(client, game, user_headers):
    class GoneSocket:
        async def send_text(self, text: str) -> None:
            raise RuntimeError("the tab closed")

    hub.rooms.setdefault(GAME, set()).add(GoneSocket())
    with client.websocket_connect(url()) as live:
        response = post(client, user_headers)
        assert response.status_code == 201
        assert live.receive_json()["type"] == "message.created" # the others still got it
    assert len(hub.rooms.get(GAME, ())) == 0 # and the dead one was dropped
