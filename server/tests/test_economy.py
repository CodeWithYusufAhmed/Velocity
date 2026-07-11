"""Economy tests: signup grant, daily bonus, rescue, money-not-spent, round limit."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import Transaction, User
from app.services import economy
from app.services.economy import EconomyError

D1, D2 = date(2026, 7, 11), date(2026, 7, 12)


async def _user(db_session, balance=0) -> User:
    u = User(email="e@example.com", display_name="Eco", balance=balance)
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.mark.asyncio
async def test_register_grants_signup_coins(client):
    r = await client.post("/auth/register", json={
        "email": "new@example.com", "display_name": "Newbie", "password": "s3cretpass"})
    assert r.json()["user"]["balance"] == 100_000


@pytest.mark.asyncio
async def test_daily_bonus_once_per_day(db_session):
    u = await _user(db_session)
    assert await economy.claim_daily_bonus(db_session, u, day=D1) == 50_000
    with pytest.raises(EconomyError, match="already claimed"):
        await economy.claim_daily_bonus(db_session, u, day=D1)
    assert await economy.claim_daily_bonus(db_session, u, day=D2) == 100_000  # next day OK


@pytest.mark.asyncio
async def test_rescue_rules(db_session):
    u = await _user(db_session, balance=199)
    for i in range(3):
        await economy.claim_rescue(db_session, u, day=D1)
        u.balance = 150  # simulate losing it again
        await db_session.commit()
    with pytest.raises(EconomyError, match="No rescues left"):
        await economy.claim_rescue(db_session, u, day=D1)
    # New day resets the cap.
    assert await economy.claim_rescue(db_session, u, day=D2) == 150 + 20_000


@pytest.mark.asyncio
async def test_rescue_requires_low_balance(db_session):
    u = await _user(db_session, balance=200)
    with pytest.raises(EconomyError, match="below 200"):
        await economy.claim_rescue(db_session, u, day=D1)


@pytest.mark.asyncio
async def test_money_not_spent_counts_only_free_coins(db_session):
    u = await _user(db_session)
    await economy.signup_grant(db_session, u)               # +100k free
    await economy.claim_daily_bonus(db_session, u, day=D1)  # +50k free
    db_session.add(Transaction(user_id=u.id, type="win", amount=999_999,
                               balance_after=u.balance + 999_999))  # winnings don't count
    await db_session.commit()
    mns = await economy.money_not_spent(db_session, u.id)
    assert mns["free_coins_received"] == 150_000
    assert mns["dollars_not_spent"] == round(150_000 / 8_000, 2)  # $18.75


@pytest.mark.asyncio
async def test_round_limit_lower_now_raise_tomorrow(db_session):
    u = await _user(db_session)
    # enable at 50 → immediate
    us = await economy.set_round_limit(db_session, u.id, 50, day=D1)
    assert us.daily_round_limit == 50 and us.pending_round_limit is None
    # lower to 10 → immediate
    us = await economy.set_round_limit(db_session, u.id, 10, day=D1)
    assert us.daily_round_limit == 10
    # raise to 100 → NOT today, pending for tomorrow
    us = await economy.set_round_limit(db_session, u.id, 100, day=D1)
    assert us.daily_round_limit == 10 and us.pending_round_limit == 100
    assert await economy.effective_round_limit(db_session, u.id, day=D1) == 10
    # next day the raise takes effect
    assert await economy.effective_round_limit(db_session, u.id, day=D2) == 100
    # disabling is immediate
    us = await economy.set_round_limit(db_session, u.id, None, day=D2)
    assert us.daily_round_limit is None
