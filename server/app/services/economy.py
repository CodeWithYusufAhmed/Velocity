"""Coin economy: signup grant, daily bonus, broke-rescue, Money-You-Didn't-Spend,
and the self-set daily round limit. All amounts flow through the transactions
ledger — a balance never changes without a ledger row.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import DailyStats, Transaction, User, UserSettings

FREE_COIN_TYPES = ("signup", "daily_bonus", "rescue")


class EconomyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def game_today() -> date:
    """The game-day boundary is midnight Asia/Dhaka, per spec."""
    return datetime.now(ZoneInfo(get_settings().game_timezone)).date()


async def get_daily_stats(session: AsyncSession, user_id: int, day: date | None = None) -> DailyStats:
    day = day or game_today()
    stats = await session.get(DailyStats, (user_id, day))
    if stats is None:
        stats = DailyStats(user_id=user_id, day=day)
        session.add(stats)
        await session.flush()
    return stats


async def _credit(session: AsyncSession, user: User, amount: int, tx_type: str, note: str | None = None) -> None:
    user.balance += amount
    session.add(
        Transaction(
            user_id=user.id, type=tx_type, amount=amount,
            balance_after=user.balance, note=note,
        )
    )


async def signup_grant(session: AsyncSession, user: User) -> None:
    """100,000 coins on account creation. Caller commits."""
    await _credit(session, user, get_settings().signup_grant, "signup")


async def claim_daily_bonus(session: AsyncSession, user: User, day: date | None = None) -> int:
    """50,000 coins, once per Asia/Dhaka day. Returns new balance."""
    stats = await get_daily_stats(session, user.id, day)
    if stats.bonus_claimed:
        raise EconomyError("Daily bonus already claimed — come back after midnight (Dhaka time)")
    stats.bonus_claimed = True
    await _credit(session, user, get_settings().daily_bonus, "daily_bonus")
    await session.commit()
    return user.balance


async def claim_rescue(session: AsyncSession, user: User, day: date | None = None) -> int:
    """20,000 coins when balance < 200, max 3/day. Returns new balance."""
    s = get_settings()
    if user.balance >= s.rescue_threshold:
        raise EconomyError("Rescue is only available when your balance is below 200")
    stats = await get_daily_stats(session, user.id, day)
    if stats.rescues_used >= s.rescue_max_per_day:
        raise EconomyError("No rescues left today — come back after midnight (Dhaka time)")
    stats.rescues_used += 1
    await _credit(session, user, s.rescue_amount, "rescue",
                  note=f"rescue {stats.rescues_used}/{s.rescue_max_per_day}")
    await session.commit()
    return user.balance


async def money_not_spent(session: AsyncSession, user_id: int) -> dict:
    """free coins received / coins_per_dollar — the point of the whole app.
    Clearly an estimate; based on the ~$1-per-8,000-coins packs Velocity replaces."""
    total = (
        await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == user_id, Transaction.type.in_(FREE_COIN_TYPES)
            )
        )
    )
    return {
        "free_coins_received": int(total),
        "dollars_not_spent": round(int(total) / get_settings().coins_per_dollar, 2),
        "estimate_note": "Estimated from typical paid-app prices (~$1 per 8,000 coins).",
    }


# ---- self-set daily round limit (anti-addiction) --------------------------

async def get_user_settings(session: AsyncSession, user_id: int) -> UserSettings:
    us = await session.get(UserSettings, user_id)
    if us is None:
        us = UserSettings(user_id=user_id)
        session.add(us)
        await session.flush()
    return us


def _resolve_pending(us: UserSettings, today: date) -> None:
    """A raise scheduled for a past/current day takes effect."""
    if us.pending_round_limit is not None and us.pending_limit_effective_date is not None:
        if us.pending_limit_effective_date <= today:
            us.daily_round_limit = us.pending_round_limit
            us.pending_round_limit = None
            us.pending_limit_effective_date = None


async def set_round_limit(
    session: AsyncSession, user_id: int, new_limit: int | None, day: date | None = None
) -> UserSettings:
    """Lowering (or turning off→on lower, or disabling) applies immediately;
    RAISING applies from the next day — the cool-down is the feature."""
    from datetime import timedelta

    today = day or game_today()
    us = await get_user_settings(session, user_id)
    _resolve_pending(us, today)

    if new_limit is not None and new_limit < 1:
        raise EconomyError("Round limit must be at least 1")

    current = us.daily_round_limit
    if new_limit is None or current is None or new_limit <= current:
        us.daily_round_limit = new_limit
        us.pending_round_limit = None
        us.pending_limit_effective_date = None
    else:
        us.pending_round_limit = new_limit
        us.pending_limit_effective_date = today + timedelta(days=1)
    await session.commit()
    return us


async def effective_round_limit(session: AsyncSession, user_id: int, day: date | None = None) -> int | None:
    us = await get_user_settings(session, user_id)
    _resolve_pending(us, day or game_today())
    return us.daily_round_limit
