"""Tables service: CRUD, live room state (chairs/members, in-memory),
role resolution, moderation actions, LiveKit token issuance.

Chair/member state is ephemeral by design — it lives in this process and
resets on server restart (rooms are live conversations, not documents).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from livekit import api as lk_api
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Table, TableBlock, TableChatBan, TableRole, User
from app.services import permissions, vip


class TableError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RoomState:
    table_id: int
    chair_count: int
    owner_id: int
    members: set[int] = field(default_factory=set)          # everyone in the room
    chairs: dict[int, int] = field(default_factory=dict)    # position -> user_id
    muted: set[int] = field(default_factory=set)            # server-side muted users


class TablesHub:
    """All live rooms in this process."""

    def __init__(self) -> None:
        self.rooms: dict[int, RoomState] = {}

    def room(self, table_id: int) -> RoomState | None:
        return self.rooms.get(table_id)


hub = TablesHub()


# ---- helpers ---------------------------------------------------------------

async def get_open_table(session: AsyncSession, table_id: int) -> Table:
    t = await session.get(Table, table_id)
    if t is None or t.status != "open":
        raise TableError("Table not found", 404)
    return t


async def role_of(session: AsyncSession, table: Table, user_id: int) -> str:
    if user_id == table.owner_id:
        return permissions.OWNER
    r = await session.scalar(
        select(TableRole).where(TableRole.table_id == table.id, TableRole.user_id == user_id)
    )
    return permissions.ADMIN if r else permissions.USER


def livekit_token(table_id: int, user: User) -> str:
    """Room-scoped LiveKit access token. API keys never ship in the app."""
    s = get_settings()
    return (
        lk_api.AccessToken(s.livekit_api_key, s.livekit_api_secret)
        .with_identity(str(user.id))
        .with_name(user.display_name)
        .with_ttl(timedelta(hours=6))
        .with_grants(lk_api.VideoGrants(
            room_join=True, room=f"table-{table_id}",
            can_publish=True, can_subscribe=True, can_publish_data=False,
        ))
        .to_jwt()
    )


async def _livekit_moderate(action: str, table_id: int, user_id: int) -> None:
    """Server-side enforcement via LiveKit's API — a modified client cannot
    dodge it. Failures are logged, not raised: DB/room state is the truth."""
    import logging
    s = get_settings()
    try:
        lk = lk_api.LiveKitAPI(url=s.livekit_url, api_key=s.livekit_api_key,
                               api_secret=s.livekit_api_secret)
        try:
            room = f"table-{table_id}"
            if action == "kick":
                await lk.room.remove_participant(
                    lk_api.RoomParticipantIdentity(room=room, identity=str(user_id)))
            elif action == "mute":
                # Mute all published audio tracks of the participant.
                p = await lk.room.get_participant(
                    lk_api.RoomParticipantIdentity(room=room, identity=str(user_id)))
                for t in p.tracks:
                    await lk.room.mute_published_track(lk_api.MuteRoomTrackRequest(
                        room=room, identity=str(user_id), track_sid=t.sid, muted=True))
        finally:
            await lk.aclose()
    except Exception:
        logging.getLogger("velocity.tables").warning(
            "LiveKit %s failed for user %s in table %s", action, user_id, table_id)


# ---- lifecycle -------------------------------------------------------------

async def _cap(session: AsyncSession, key: str, default: int) -> int:
    """Capacity cap: runtime_settings override (admin dashboard) else .env default."""
    from app.models import RuntimeSetting
    row = await session.get(RuntimeSetting, key)
    try:
        return int(row.value) if row else default
    except ValueError:
        return default


async def create_table(session: AsyncSession, owner: User, name: str,
                       topic: str | None, chair_count: int) -> Table:
    if chair_count not in (8, 10, 12):
        raise TableError("Chair count must be 8, 10 or 12")
    open_count = len(hub.rooms)
    if open_count >= await _cap(session, "max_tables", get_settings().max_tables):
        raise TableError("Server is at its table capacity right now", 503)
    t = Table(owner_id=owner.id, name=name.strip(), topic=(topic or "").strip() or None,
              chair_count=chair_count)
    session.add(t)
    await session.commit()
    hub.rooms[t.id] = RoomState(table_id=t.id, chair_count=chair_count, owner_id=owner.id)
    return t


async def join_table(session: AsyncSession, table_id: int, user: User) -> dict:
    t = await get_open_table(session, table_id)
    blocked = await session.scalar(select(TableBlock).where(
        TableBlock.table_id == table_id, TableBlock.user_id == user.id))
    if blocked:
        # Owner block overrides everything, including VIP Anti-Kick.
        raise TableError("You are blocked from this Table", 403)
    room = hub.rooms.setdefault(
        t.id, RoomState(table_id=t.id, chair_count=t.chair_count, owner_id=t.owner_id))
    if len(room.members) >= await _cap(session, "max_listeners_per_table",
                                       get_settings().max_listeners_per_table):
        raise TableError("This Table is full right now", 503)
    room.members.add(user.id)
    tier = await vip.active_tier(session, user.id)
    return {
        "livekit_token": livekit_token(t.id, user),
        "livekit_url": get_settings().livekit_url,
        "role": await role_of(session, t, user.id),
        "vip_tier": tier,  # client plays the VIP2+ welcome effect from this
        "chairs": room.chairs, "chair_count": room.chair_count,
    }


def leave_table(table_id: int, user_id: int) -> None:
    room = hub.room(table_id)
    if room:
        room.members.discard(user_id)
        room.chairs = {p: u for p, u in room.chairs.items() if u != user_id}


def sit(table_id: int, user_id: int, position: int) -> None:
    room = hub.room(table_id)
    if not room or user_id not in room.members:
        raise TableError("Join the table first")
    if not 0 <= position < room.chair_count:
        raise TableError("No such chair")
    if room.chairs.get(position):
        raise TableError("Chair is taken")
    room.chairs = {p: u for p, u in room.chairs.items() if u != user_id}  # one chair max
    room.chairs[position] = user_id


def stand(table_id: int, user_id: int) -> None:
    room = hub.room(table_id)
    if room:
        room.chairs = {p: u for p, u in room.chairs.items() if u != user_id}


# ---- moderation ------------------------------------------------------------

async def _actor_target_roles(session: AsyncSession, table: Table,
                              actor_id: int, target_id: int) -> tuple[str, str]:
    return await role_of(session, table, actor_id), await role_of(session, table, target_id)


async def kick(session: AsyncSession, table_id: int, actor_id: int, target_id: int) -> dict:
    t = await get_open_table(session, table_id)
    actor_role, target_role = await _actor_target_roles(session, t, actor_id, target_id)
    verdict = permissions.can_kick(actor_role, target_role, await vip.active_tier(session, target_id))
    if verdict == "forbidden":
        raise TableError("You cannot kick this user", 403)
    if verdict == "anti_kick":
        return {"kicked": False, "reason": "This user has Anti-Kick"}
    leave_table(table_id, target_id)
    await _livekit_moderate("kick", table_id, target_id)
    return {"kicked": True}


async def mute(session: AsyncSession, table_id: int, actor_id: int, target_id: int) -> dict:
    t = await get_open_table(session, table_id)
    actor_role, target_role = await _actor_target_roles(session, t, actor_id, target_id)
    if permissions.can_mute(actor_role, target_role) != "ok":
        raise TableError("You cannot mute this user", 403)
    room = hub.room(table_id)
    if room:
        room.muted.add(target_id)
    await _livekit_moderate("mute", table_id, target_id)
    return {"muted": True}


async def block(session: AsyncSession, table_id: int, actor_id: int, target_id: int) -> dict:
    t = await get_open_table(session, table_id)
    actor_role, target_role = await _actor_target_roles(session, t, actor_id, target_id)
    if permissions.can_block(actor_role, target_role) != "ok":
        raise TableError("Only the owner can block users from a Table", 403)
    exists = await session.scalar(select(TableBlock).where(
        TableBlock.table_id == table_id, TableBlock.user_id == target_id))
    if not exists:
        session.add(TableBlock(table_id=table_id, user_id=target_id, blocked_by=actor_id))
        await session.commit()
    leave_table(table_id, target_id)          # block also removes — overrides Anti-Kick
    await _livekit_moderate("kick", table_id, target_id)
    return {"blocked": True}


async def chat_ban(session: AsyncSession, table_id: int, actor_id: int, target_id: int) -> dict:
    t = await get_open_table(session, table_id)
    actor_role, target_role = await _actor_target_roles(session, t, actor_id, target_id)
    if permissions.can_chat_ban(actor_role, target_role) != "ok":
        raise TableError("You cannot chat-ban this user", 403)
    exists = await session.scalar(select(TableChatBan).where(
        TableChatBan.table_id == table_id, TableChatBan.user_id == target_id))
    if not exists:
        session.add(TableChatBan(table_id=table_id, user_id=target_id, banned_by=actor_id))
        await session.commit()
    return {"chat_banned": True}


async def grant_admin(session: AsyncSession, table_id: int, actor_id: int,
                      target_id: int, grant: bool) -> dict:
    t = await get_open_table(session, table_id)
    if permissions.can_grant_admin(await role_of(session, t, actor_id)) != "ok":
        raise TableError("Only the owner can manage admins", 403)
    if target_id == t.owner_id:
        raise TableError("The owner cannot be made an admin", 400)
    existing = await session.scalar(select(TableRole).where(
        TableRole.table_id == table_id, TableRole.user_id == target_id))
    if grant and not existing:
        session.add(TableRole(table_id=table_id, user_id=target_id, granted_by=actor_id))
    elif not grant and existing:
        await session.delete(existing)
    await session.commit()
    return {"admin": grant}


async def close_table(session: AsyncSession, table_id: int, actor_id: int) -> None:
    t = await get_open_table(session, table_id)
    if permissions.can_close_table(await role_of(session, t, actor_id)) != "ok":
        raise TableError("Only the owner can close the Table", 403)
    t.status, t.closed_at = "closed", datetime.now(timezone.utc)
    await session.commit()
    hub.rooms.pop(table_id, None)


async def is_chat_banned(session: AsyncSession, table_id: int, user_id: int) -> bool:
    return (await session.scalar(select(TableChatBan).where(
        TableChatBan.table_id == table_id, TableChatBan.user_id == user_id))) is not None
