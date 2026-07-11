"""The daily round limit enforced inside the engine's place_bet."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.game.engine import BetError, GameEngine
from app.services import economy
from tests.test_engine import _seed_odds_and_user


@pytest.mark.asyncio
async def test_round_limit_blocks_new_rounds_not_same_round(test_engine, db_session):
    user = await _seed_odds_and_user(db_session)
    await economy.set_round_limit(db_session, user.id, 1)

    eng = GameEngine(async_sessionmaker(test_engine, expire_on_commit=False))
    await eng.load_slots()

    await eng.open_round()
    await eng.place_bet(user.id, 0, 200)   # round 1 of 1 — allowed
    await eng.place_bet(user.id, 1, 200)   # same round, more bets — still allowed
    await eng.settle_round()

    await eng.open_round()                  # a second round today
    with pytest.raises(BetError, match="daily round limit"):
        await eng.place_bet(user.id, 0, 200)
