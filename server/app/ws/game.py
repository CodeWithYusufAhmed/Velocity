"""/ws/game — realtime game channel.

Server → client: round_state (1/s), spin_result, bet_ack, balance_update, error.
Client → server: {"type": "place_bet", "slot": int, "amount": int}.
Auth: ?token=<access JWT> (WebSocket headers are awkward on Android's OkHttp).
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.game.engine import BetError, GameEngine
from app.security import decode_access_token

log = logging.getLogger("velocity.ws.game")
router = APIRouter()


class GameHub:
    """Fans engine broadcasts out to every connected socket."""

    def __init__(self) -> None:
        self.sockets: set[WebSocket] = set()

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.sockets.discard(ws)


hub = GameHub()


def get_engine(ws: WebSocket) -> GameEngine | None:
    return getattr(ws.app.state, "engine", None)


@router.websocket("/ws/game")
async def ws_game(ws: WebSocket, token: str = ""):
    user_id = decode_access_token(token)
    if user_id is None:
        await ws.close(code=4401)  # unauthorized
        return
    engine = get_engine(ws)
    if engine is None:
        await ws.close(code=1013)  # try again later
        return

    await ws.accept()
    hub.sockets.add(ws)
    # Immediate snapshot so the client can render without waiting for the tick.
    st = engine.state
    await ws.send_json(
        {
            "type": "round_state", "phase": st.phase, "round_id": st.round_id,
            "seconds_left": st.seconds_left, "commit": st.commit,
        }
    )
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "place_bet":
                try:
                    ack = await engine.place_bet(
                        user_id, int(msg.get("slot", -1)), int(msg.get("amount", 0))
                    )
                    await ws.send_json(
                        {
                            "type": "bet_ack", "round_id": engine.state.round_id,
                            "slot": msg["slot"], "amount": msg["amount"], **ack,
                        }
                    )
                except (BetError, ValueError) as e:
                    await ws.send_json({"type": "error", "message": str(e)})
            else:
                await ws.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.sockets.discard(ws)
