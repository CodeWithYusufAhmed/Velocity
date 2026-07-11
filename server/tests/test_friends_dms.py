"""Friends lifecycle, VIP friend limits + grandfather rule, store-and-forward DMs."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Friendship, PendingMessage, User, VipStatus
from app.services import dms, friends, safety
from app.services.dms import DmError
from app.services.friends import FriendError
from app.ws.social import social_hub


async def _users(db_session, n) -> list[User]:
    users = [User(email=f"f{i}@example.com", display_name=f"F{i}", balance=0) for i in range(n)]
    db_session.add_all(users)
    await db_session.commit()
    return users


async def _befriend(db_session, a: User, b: User):
    fr = await friends.send_request(db_session, a.id, b.id)
    await friends.accept(db_session, fr.id, b.id)


@pytest.fixture(autouse=True)
def offline_hub():
    social_hub.by_user.clear()
    yield
    social_hub.by_user.clear()


class FakeWs:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)


# ---- friends ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_lifecycle(db_session):
    a, b, c = await _users(db_session, 3)
    fr = await friends.send_request(db_session, a.id, b.id)
    with pytest.raises(FriendError, match="pending"):
        await friends.send_request(db_session, b.id, a.id)  # reverse dup blocked
    with pytest.raises(FriendError, match="Not your request"):
        await friends.accept(db_session, fr.id, c.id)
    await friends.accept(db_session, fr.id, b.id)
    assert await friends.are_friends(db_session, a.id, b.id)
    with pytest.raises(FriendError, match="Already friends"):
        await friends.send_request(db_session, a.id, b.id)

    fr2 = await friends.send_request(db_session, a.id, c.id)
    await friends.cancel(db_session, fr2.id, a.id)          # sender cancels
    fr3 = await friends.send_request(db_session, a.id, c.id)
    await friends.decline(db_session, fr3.id, c.id)         # recipient declines
    assert not await friends.are_friends(db_session, a.id, c.id)

    await friends.unfriend(db_session, a.id, b.id)
    assert not await friends.are_friends(db_session, a.id, b.id)


@pytest.mark.asyncio
async def test_blocked_users_cannot_request(db_session):
    a, b = await _users(db_session, 2)
    await safety.block_user(db_session, b.id, a.id)
    with pytest.raises(FriendError, match="Cannot send"):
        await friends.send_request(db_session, a.id, b.id)


@pytest.mark.asyncio
async def test_friend_limit_and_grandfather_rule(db_session, monkeypatch):
    # Shrink limits so the test stays fast: base 2, VIP3 4.
    monkeypatch.setattr("app.services.vip.FRIEND_LIMITS",
                        {0: 2, 1: 2, 2: 2, 3: 4, 4: 5, 5: 6})
    users = await _users(db_session, 6)
    me = users[0]

    await _befriend(db_session, me, users[1])
    await _befriend(db_session, me, users[2])
    with pytest.raises(FriendError, match="Friend limit"):      # base limit 2 hit
        await friends.send_request(db_session, me.id, users[3].id)

    # VIP3 raises the limit to 4 → adding works again.
    db_session.add(VipStatus(user_id=me.id, tier=3,
                             awarded_at=datetime.now(timezone.utc),
                             expires_at=datetime.now(timezone.utc) + timedelta(days=3)))
    await db_session.commit()
    await _befriend(db_session, me, users[3])
    await _befriend(db_session, me, users[4])
    assert await friends.friend_count(db_session, me.id) == 4

    # VIP expires → limit back to 2, but the 4 friends are GRANDFATHERED.
    status = await db_session.get(VipStatus, me.id)
    status.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    assert await friends.friend_count(db_session, me.id) == 4    # nobody deleted
    with pytest.raises(FriendError, match="Friend limit"):       # but no new adds
        await friends.send_request(db_session, me.id, users[5].id)


# ---- DMs ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dm_online_relay_stores_nothing(db_session):
    a, b = await _users(db_session, 2)
    ws = FakeWs()
    social_hub.by_user[b.id] = ws
    result = await dms.send_dm(db_session, a, b.id, "hello!")
    assert result == {"delivered": True}
    assert ws.sent[0]["type"] == "dm_incoming" and ws.sent[0]["text"] == "hello!"
    assert (await db_session.scalar(select(PendingMessage))) is None  # nothing stored


@pytest.mark.asyncio
async def test_dm_offline_queue_and_delete_on_delivery(db_session):
    a, b = await _users(db_session, 2)
    result = await dms.send_dm(db_session, a, b.id, "offline msg")
    assert result == {"delivered": False}
    assert (await db_session.scalar(select(PendingMessage))) is not None

    ws = FakeWs()
    social_hub.by_user[b.id] = ws
    delivered = await dms.deliver_pending(db_session, b.id)
    assert delivered == 1
    assert ws.sent[0]["text"] == "offline msg"
    assert (await db_session.scalar(select(PendingMessage))) is None  # deleted on delivery


@pytest.mark.asyncio
async def test_dm_blocked_and_validation(db_session):
    a, b = await _users(db_session, 2)
    await safety.block_user(db_session, b.id, a.id)  # b blocked a
    with pytest.raises(DmError, match="cannot message"):
        await dms.send_dm(db_session, a, b.id, "hi")
    with pytest.raises(DmError, match="yourself"):
        await dms.send_dm(db_session, a, a.id, "hi")
    with pytest.raises(DmError, match="Empty"):
        await dms.send_dm(db_session, a, b.id, "   ")


@pytest.mark.asyncio
async def test_dm_purge_after_30_days(db_session):
    a, b = await _users(db_session, 2)
    await dms.send_dm(db_session, a, b.id, "old")
    row = await db_session.scalar(select(PendingMessage))
    purged = await dms.purge_expired(
        db_session, now=row.created_at + timedelta(days=31))
    assert purged == 1
    # A fresh one survives the purge.
    await dms.send_dm(db_session, a, b.id, "new")
    assert await dms.purge_expired(db_session) == 0
    assert (await db_session.scalar(select(PendingMessage))).body == "new"
