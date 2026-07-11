"""VIP engine tests: thresholds, replacement (no stacking), expiry, grandfather limits."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import User, VipStatus
from app.services import vip

DAY = date(2026, 7, 11)
NOW = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)


async def _user(db_session) -> User:
    u = User(email="v@example.com", display_name="Vip", balance=0)
    db_session.add(u)
    await db_session.commit()
    return u


def test_tier_thresholds():
    assert vip.tier_for_winnings(999_999) == 0
    assert vip.tier_for_winnings(1_000_000) == 1
    assert vip.tier_for_winnings(2_500_000) == 2
    assert vip.tier_for_winnings(5_000_000) == 5
    assert vip.tier_for_winnings(50_000_000) == 5


def test_friend_limits_and_anti_kick():
    assert [vip.friend_limit(t) for t in range(6)] == [500, 500, 500, 1000, 2000, 5000]
    assert not vip.has_anti_kick(2)
    assert vip.has_anti_kick(3) and vip.has_anti_kick(5)


@pytest.mark.asyncio
async def test_crossing_threshold_awards_tier(db_session):
    u = await _user(db_session)
    assert await vip.record_winnings(db_session, u.id, 999_999, day=DAY, now=NOW) == 0
    assert await vip.record_winnings(db_session, u.id, 1, day=DAY, now=NOW) == 1  # cumulative
    status = await db_session.get(VipStatus, u.id)
    assert status.tier == 1
    assert status.expires_at == NOW + timedelta(days=1)


@pytest.mark.asyncio
async def test_higher_tier_replaces_immediately_no_stacking(db_session):
    u = await _user(db_session)
    await vip.record_winnings(db_session, u.id, 2_000_000, day=DAY, now=NOW)  # VIP2 (2 days)
    later = NOW + timedelta(hours=6)
    tier = await vip.record_winnings(db_session, u.id, 1_000_000, day=DAY, now=later)  # total 3M → VIP3
    assert tier == 3
    status = await db_session.get(VipStatus, u.id)
    # VIP3 for exactly 3 days from the award moment — VIP2 remainder is gone.
    assert status.tier == 3
    assert status.awarded_at == later
    assert status.expires_at == later + timedelta(days=3)


@pytest.mark.asyncio
async def test_lower_or_equal_tier_never_downgrades(db_session):
    u = await _user(db_session)
    await vip.record_winnings(db_session, u.id, 5_000_000, day=DAY, now=NOW)  # VIP5
    # More winnings the same day (still ≥5M → tier 5): no change to expiry.
    status_before = (await db_session.get(VipStatus, u.id)).expires_at
    await vip.record_winnings(db_session, u.id, 1_000_000, day=DAY, now=NOW + timedelta(hours=1))
    status = await db_session.get(VipStatus, u.id)
    assert status.tier == 5 and status.expires_at == status_before


@pytest.mark.asyncio
async def test_expiry_and_new_day_counter(db_session):
    u = await _user(db_session)
    await vip.record_winnings(db_session, u.id, 1_000_000, day=DAY, now=NOW)  # VIP1, 1 day
    assert await vip.active_tier(db_session, u.id, now=NOW + timedelta(hours=23)) == 1
    assert await vip.active_tier(db_session, u.id, now=NOW + timedelta(days=1, seconds=1)) == 0
    # Next day's counter starts fresh: 900k that day is not enough for VIP1.
    next_day = DAY + timedelta(days=1)
    tier = await vip.record_winnings(
        db_session, u.id, 900_000, day=next_day, now=NOW + timedelta(days=1, hours=1)
    )
    assert tier == 0
