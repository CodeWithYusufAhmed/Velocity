"""Tables service integration tests: lifecycle, chairs, moderation flows,
Anti-Kick vs owner block, reports & personal blocks."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import TableBlock, User, VipStatus
from app.services import safety, tables as svc
from app.services.safety import SafetyError
from app.services.tables import TableError, hub


async def _users(db_session, n=3) -> list[User]:
    users = [User(email=f"u{i}@example.com", display_name=f"U{i}", balance=0) for i in range(n)]
    db_session.add_all(users)
    await db_session.commit()
    return users


@pytest.fixture(autouse=True)
def clean_hub():
    hub.rooms.clear()
    yield
    hub.rooms.clear()


@pytest.mark.asyncio
async def test_create_join_sit_stand_leave(db_session):
    owner, member, _ = await _users(db_session)
    t = await svc.create_table(db_session, owner, "Chill", "cars", 8)

    info = await svc.join_table(db_session, t.id, member)
    assert info["livekit_token"] and info["role"] == "user"

    svc.sit(t.id, member.id, 3)
    assert hub.room(t.id).chairs[3] == member.id
    svc.sit(t.id, member.id, 5)  # moving chairs frees the old one
    assert 3 not in hub.room(t.id).chairs and hub.room(t.id).chairs[5] == member.id

    with pytest.raises(TableError, match="taken"):
        other = await svc.join_table(db_session, t.id, owner)
        svc.sit(t.id, owner.id, 5)

    svc.stand(t.id, member.id)
    assert member.id not in hub.room(t.id).chairs.values()
    svc.leave_table(t.id, member.id)
    assert member.id not in hub.room(t.id).members


@pytest.mark.asyncio
async def test_invalid_chair_count_rejected(db_session):
    (owner,) = await _users(db_session, 1)
    with pytest.raises(TableError, match="8, 10 or 12"):
        await svc.create_table(db_session, owner, "Bad", None, 9)


@pytest.mark.asyncio
async def test_admin_kick_fails_vs_anti_kick_but_owner_block_works(db_session):
    owner, admin, vip3 = await _users(db_session)
    t = await svc.create_table(db_session, owner, "T", None, 8)
    await svc.grant_admin(db_session, t.id, owner.id, admin.id, grant=True)
    db_session.add(VipStatus(user_id=vip3.id, tier=3,
                             awarded_at=datetime.now(timezone.utc),
                             expires_at=datetime.now(timezone.utc) + timedelta(days=3)))
    await db_session.commit()
    await svc.join_table(db_session, t.id, vip3)

    # Admin kick → fails silently with the Anti-Kick notice; user stays.
    result = await svc.kick(db_session, t.id, admin.id, vip3.id)
    assert result == {"kicked": False, "reason": "This user has Anti-Kick"}
    assert vip3.id in hub.room(t.id).members

    # Owner block → removes and bars re-entry, even for VIP3+.
    result = await svc.block(db_session, t.id, owner.id, vip3.id)
    assert result == {"blocked": True}
    assert vip3.id not in hub.room(t.id).members
    with pytest.raises(TableError, match="blocked"):
        await svc.join_table(db_session, t.id, vip3)


@pytest.mark.asyncio
async def test_admin_cannot_touch_admin_or_owner(db_session):
    owner, a1, a2 = await _users(db_session)
    t = await svc.create_table(db_session, owner, "T", None, 8)
    for a in (a1, a2):
        await svc.grant_admin(db_session, t.id, owner.id, a.id, grant=True)
    for target in (a2.id, owner.id):
        with pytest.raises(TableError):
            await svc.kick(db_session, t.id, a1.id, target)
        with pytest.raises(TableError):
            await svc.mute(db_session, t.id, a1.id, target)
        with pytest.raises(TableError):
            await svc.block(db_session, t.id, a1.id, target)


@pytest.mark.asyncio
async def test_chat_ban_and_close(db_session):
    owner, member, _ = await _users(db_session)
    t = await svc.create_table(db_session, owner, "T", None, 10)
    await svc.join_table(db_session, t.id, member)
    await svc.chat_ban(db_session, t.id, owner.id, member.id)
    assert await svc.is_chat_banned(db_session, t.id, member.id)

    with pytest.raises(TableError, match="owner"):
        await svc.close_table(db_session, t.id, member.id)
    await svc.close_table(db_session, t.id, owner.id)
    assert hub.room(t.id) is None
    with pytest.raises(TableError, match="not found"):
        await svc.join_table(db_session, t.id, member)


@pytest.mark.asyncio
async def test_reports_and_personal_blocks(db_session):
    a, b, _ = await _users(db_session)
    r = await safety.report_user(db_session, a.id, b.id, "spam", "note", None)
    assert r.id and r.status == "open"
    with pytest.raises(SafetyError):
        await safety.report_user(db_session, a.id, a.id, "spam", None, None)

    await safety.block_user(db_session, a.id, b.id)
    await safety.block_user(db_session, a.id, b.id)  # idempotent
    assert await safety.blocked_ids(db_session, a.id) == {b.id}
    await safety.unblock_user(db_session, a.id, b.id)
    assert await safety.blocked_ids(db_session, a.id) == set()
