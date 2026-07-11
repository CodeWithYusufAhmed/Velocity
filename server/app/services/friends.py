"""Friends: request lifecycle + VIP friend limits with the grandfather rule.

Grandfather rule: the limit is enforced only when ADDING a friend. When VIP
expires and the limit drops below the current friend count, nothing is deleted —
the user simply cannot add more until they are under the limit again.
"""

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FriendRequest, Friendship, User
from app.services import vip


class FriendError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


async def friend_count(session: AsyncSession, user_id: int) -> int:
    return await session.scalar(
        select(func.count()).select_from(Friendship).where(
            or_(Friendship.user_a_id == user_id, Friendship.user_b_id == user_id))
    )


async def friend_ids(session: AsyncSession, user_id: int) -> list[int]:
    rows = (await session.execute(
        select(Friendship.user_a_id, Friendship.user_b_id).where(
            or_(Friendship.user_a_id == user_id, Friendship.user_b_id == user_id)))).all()
    return [b if a == user_id else a for a, b in rows]


async def are_friends(session: AsyncSession, a: int, b: int) -> bool:
    pa, pb = _pair(a, b)
    return (await session.scalar(select(Friendship).where(
        Friendship.user_a_id == pa, Friendship.user_b_id == pb))) is not None


async def _check_can_add(session: AsyncSession, user_id: int) -> None:
    limit = vip.friend_limit(await vip.active_tier(session, user_id))
    if await friend_count(session, user_id) >= limit:
        raise FriendError(f"Friend limit reached ({limit}). Existing friends are kept.", 409)


async def send_request(session: AsyncSession, sender_id: int, recipient_id: int) -> FriendRequest:
    from app.services.safety import blocked_ids
    if sender_id == recipient_id:
        raise FriendError("You cannot friend yourself")
    if await session.get(User, recipient_id) is None:
        raise FriendError("User not found", 404)
    if await are_friends(session, sender_id, recipient_id):
        raise FriendError("Already friends")
    if recipient_id in await blocked_ids(session, sender_id) or \
       sender_id in await blocked_ids(session, recipient_id):
        raise FriendError("Cannot send a request to this user", 403)
    pending = await session.scalar(select(FriendRequest).where(
        FriendRequest.status == "pending",
        or_((FriendRequest.sender_id == sender_id) & (FriendRequest.recipient_id == recipient_id),
            (FriendRequest.sender_id == recipient_id) & (FriendRequest.recipient_id == sender_id))))
    if pending:
        raise FriendError("A request is already pending")
    await _check_can_add(session, sender_id)  # sender must have room now
    fr = FriendRequest(sender_id=sender_id, recipient_id=recipient_id)
    session.add(fr)
    await session.commit()
    return fr


async def _get_pending(session: AsyncSession, request_id: int) -> FriendRequest:
    fr = await session.get(FriendRequest, request_id)
    if fr is None or fr.status != "pending":
        raise FriendError("Request not found", 404)
    return fr


async def accept(session: AsyncSession, request_id: int, actor_id: int) -> None:
    fr = await _get_pending(session, request_id)
    if fr.recipient_id != actor_id:
        raise FriendError("Not your request", 403)
    # BOTH sides need room at accept time (limits may have changed since sending).
    await _check_can_add(session, fr.recipient_id)
    await _check_can_add(session, fr.sender_id)
    fr.status, fr.resolved_at = "accepted", datetime.now(timezone.utc)
    a, b = _pair(fr.sender_id, fr.recipient_id)
    session.add(Friendship(user_a_id=a, user_b_id=b))
    await session.commit()


async def decline(session: AsyncSession, request_id: int, actor_id: int) -> None:
    fr = await _get_pending(session, request_id)
    if fr.recipient_id != actor_id:
        raise FriendError("Not your request", 403)
    fr.status, fr.resolved_at = "declined", datetime.now(timezone.utc)
    await session.commit()


async def cancel(session: AsyncSession, request_id: int, actor_id: int) -> None:
    fr = await _get_pending(session, request_id)
    if fr.sender_id != actor_id:
        raise FriendError("Not your request", 403)
    fr.status, fr.resolved_at = "cancelled", datetime.now(timezone.utc)
    await session.commit()


async def unfriend(session: AsyncSession, user_id: int, other_id: int) -> None:
    a, b = _pair(user_id, other_id)
    row = await session.scalar(select(Friendship).where(
        Friendship.user_a_id == a, Friendship.user_b_id == b))
    if row:
        await session.delete(row)
        await session.commit()
