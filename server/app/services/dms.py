"""Store-and-forward direct messages (spec B4).

History lives on the users' DEVICES (Room DB), not this server:
- recipient online  → relay instantly over /ws/social, store NOTHING;
- recipient offline → row in pending_messages, deleted the moment it is delivered;
- rows older than 30 days are purged by a scheduled job.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PendingMessage, User

PURGE_AFTER_DAYS = 30


class DmError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _payload(sender: User, text: str, sent_at: str | None = None) -> dict:
    return {
        "type": "dm_incoming", "sender_id": sender.id,
        "sender_name": sender.display_name, "text": text,
        "sent_at": sent_at or datetime.now(timezone.utc).isoformat(),
    }


async def send_dm(session: AsyncSession, sender: User, recipient_id: int, text: str) -> dict:
    """Returns {"delivered": bool} — True means relayed live, False means queued."""
    from app.services.safety import blocked_ids
    from app.ws.social import social_hub

    text = text.strip()[:2000]
    if not text:
        raise DmError("Empty message")
    if sender.id == recipient_id:
        raise DmError("You cannot message yourself")
    if await session.get(User, recipient_id) is None:
        raise DmError("User not found", 404)
    # Blocked users cannot message you — checked both directions.
    if sender.id in await blocked_ids(session, recipient_id) or \
       recipient_id in await blocked_ids(session, sender.id):
        raise DmError("You cannot message this user", 403)

    if social_hub.is_online(recipient_id):
        if await social_hub.send_to(recipient_id, _payload(sender, text)):
            return {"delivered": True}
    session.add(PendingMessage(sender_id=sender.id, recipient_id=recipient_id, body=text))
    await session.commit()
    return {"delivered": False}


async def deliver_pending(session: AsyncSession, user_id: int) -> int:
    """Called when a user connects: push queued DMs, then delete them immediately."""
    from app.ws.social import social_hub

    rows = (await session.scalars(
        select(PendingMessage).where(PendingMessage.recipient_id == user_id)
        .order_by(PendingMessage.created_at))).all()
    delivered = 0
    for m in rows:
        sender = await session.get(User, m.sender_id)
        ok = await social_hub.send_to(
            user_id, _payload(sender, m.body, m.created_at.isoformat()))
        if not ok:
            break  # socket dropped mid-delivery; keep the rest queued
        await session.delete(m)  # delete-on-delivery — the server keeps nothing
        delivered += 1
    await session.commit()
    return delivered


async def purge_expired(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduled job: purge pending messages older than 30 days."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=PURGE_AFTER_DAYS)
    result = await session.execute(
        delete(PendingMessage).where(PendingMessage.created_at < cutoff))
    await session.commit()
    return result.rowcount
