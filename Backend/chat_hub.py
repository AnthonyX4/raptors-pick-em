from fastapi import WebSocket
from pydantic import BaseModel


class ChatHub:
    """Which sockets are listening to which game's chat, and a way to send to all of them.

    Lives in this process's memory, so it only works with one api process. With more, each room would split
    in two, one half per process. That's when redis pub/sub goes behind broadcast() and nothing else changes.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(game_id, set()).add(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        sockets = self.rooms.get(game_id)
        if sockets is None:
            return
        sockets.discard(websocket) # discard, not remove: broadcast() may have dropped it already
        if not sockets:
            del self.rooms[game_id] # so the dict doesn't keep an empty entry for every game ever opened

    async def broadcast(self, game_id: str, event: BaseModel) -> None:
        # a copy, because disconnect() changes the set while we loop. serialized once, not once per socket
        message = event.model_dump_json()
        for websocket in list(self.rooms.get(game_id, ())):
            try:
                await websocket.send_text(message)
            except Exception:
                # a tab that closed mid-broadcast must never turn someone's POST into a 500
                self.disconnect(game_id, websocket)


hub = ChatHub() # the one hub for this process
