"""VIP engine. Tiers are EARNED by coins won within one Asia/Dhaka day —
never bought (Prime Directive 1).

Rules implemented here:
- Threshold crossing awards the tier instantly.
- A HIGHER tier replaces the current one immediately; durations never stack.
- Equal/lower tier while one is active: no change.
- Expiry is just a timestamp comparison — computed server-side, client displays.
- Friend limits: base 500; VIP3 1,000; VIP4 2,000; VIP5 5,000. When VIP expires
  the limit drops but existing friends are never deleted (grandfather rule —
  enforced by the friends service in M6 via can_add_friend()).
"""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyWinningsCounter, VipStatus
from app.services.economy import game_today

# tier -> (daily winnings threshold, duration days)
TIERS: dict[int, tuple[int, int]] = {
    1: (1_000_000, 1),
    2: (2_000_000, 2),
    3: (3_000_000, 3),
    4: (4_000_000, 4),
    5: (5_000_000, 5),
}
BASE_FRIEND_LIMIT = 500
FRIEND_LIMITS = {0: BASE_FRIEND_LIMIT, 1: BASE_FRIEND_LIMIT, 2: BASE_FRIEND_LIMIT,
                 3: 1_000, 4: 2_000, 5: 5_000}
ANTI_KICK_MIN_TIER = 3


def tier_for_winnings(coins_won_today: int) -> int:
    """Highest tier whose threshold is met (0 = none)."""
    tier = 0
    for t, (threshold, _) in TIERS.items():
        if coins_won_today >= threshold:
            tier = t
    return tier


async def active_tier(session: AsyncSession, user_id: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    status = await session.get(VipStatus, user_id)
    if status is None or status.expires_at < now:
        return 0
    return status.tier


def friend_limit(tier: int) -> int:
    return FRIEND_LIMITS.get(tier, BASE_FRIEND_LIMIT)


def has_anti_kick(tier: int) -> bool:
    return tier >= ANTI_KICK_MIN_TIER


async def record_winnings(
    session: AsyncSession,
    user_id: int,
    amount: int,
    day: date | None = None,
    now: datetime | None = None,
) -> int:
    """Add won coins to today's counter and award/upgrade VIP if a threshold
    is crossed. Returns the (possibly new) active tier. Caller commits."""
    day = day or game_today()
    now = now or datetime.now(timezone.utc)

    counter = await session.get(DailyWinningsCounter, (user_id, day))
    if counter is None:
        counter = DailyWinningsCounter(user_id=user_id, day=day, coins_won=0)
        session.add(counter)
    counter.coins_won += amount

    earned = tier_for_winnings(counter.coins_won)
    current = await active_tier(session, user_id, now)
    if earned > current:
        _, duration_days = TIERS[earned]
        status = await session.get(VipStatus, user_id)
        expires = now + timedelta(days=duration_days)
        if status is None:
            session.add(VipStatus(user_id=user_id, tier=earned, awarded_at=now, expires_at=expires))
        else:  # replace immediately — days do NOT stack
            status.tier, status.awarded_at, status.expires_at = earned, now, expires
        return earned
    return current
