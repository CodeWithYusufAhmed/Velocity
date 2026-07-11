"""/ws/social — realtime social channel (M5: table chat + table events;
M6 adds DMs, friends, presence).

Client → server: {"type": "table_chat_send", "table_id": int, "text": str}
Server → client: table_chat_message, table_event, error.
Personal blocks are respected: you never receive messages from users you blocked.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import SessionLocal
from app.models import User
from app.security import decode_access_token
from app.services import safety, tables as tables_svc, vip

log = logging.getLogger("velocity.ws.social")
router = APIRouter()


class SocialHub:
    def __init__(self) -> None:
        self.by_user: dict[int, WebSocket] = {}

    def is_online(self, user_id: int) -> bool:
        return user_id in self.by_user

    async def send_to(self, user_id: int, message: dict) -> bool:
        ws = self.by_user.get(user_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            self.by_user.pop(user_id, None)
            return False


social_hub = SocialHub()


async def notify_table(table_id: int, message: dict, exclude_for: int | None = None) -> None:
    """Send an event to every online member of a table. exclude_for: author id
    used for block filtering (recipients who blocked the author are skipped)."""
    room = tables_svc.hub.room(table_id)
    if not room:
        return
    if exclude_for is None:
        for uid in list(room.members):
            await social_hub.send_to(uid, message)
        return
    async with SessionLocal() as s:
        for uid in list(room.members):
            if exclude_for != uid and exclude_for in await safety.blocked_ids(s, uid):
                continue
            await social_hub.send_to(uid, message)


@router.websocket("/ws/social")
async def ws_social(ws: WebSocket, token: str = ""):
    user_id = decode_access_token(token)
    if user_id is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    social_hub.by_user[user_id] = ws
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "table_chat_send":
                await _handle_chat(ws, user_id, msg)
            else:
                await ws.send_json({"type": "error", "message": "Unknown message type"})
    except WebSocketDisconnect:
        pass
    finally:
        if social_hub.by_user.get(user_id) is ws:
            social_hub.by_user.pop(user_id, None)


async def _handle_chat(ws: WebSocket, user_id: int, msg: dict) -> None:
    table_id = msg.get("table_id")
    text = (msg.get("text") or "").strip()[:500]
    room = tables_svc.hub.room(table_id) if isinstance(table_id, int) else None
    if not room or user_id not in room.members:
        await ws.send_json({"type": "error", "message": "You are not in this Table"})
        return
    if not text:
        return
    async with SessionLocal() as s:
        if await tables_svc.is_chat_banned(s, table_id, user_id):
            await ws.send_json({"type": "error", "message": "You are banned from this chat"})
            return
        user = await s.get(User, user_id)
        tier = await vip.active_tier(s, user_id)
    await notify_table(
        table_id,
        {"type": "table_chat_message", "table_id": table_id, "user_id": user_id,
         "display_name": user.display_name, "vip_tier": tier, "text": text},
        exclude_for=user_id,
    )
