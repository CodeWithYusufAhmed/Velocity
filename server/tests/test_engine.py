"""Round engine integration tests against the test database."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.game import rng
from app.game.engine import BetError, GameEngine, BETTING
from app.models import Bet, OddsSlot, Round, Transaction, User
from app.game.odds import SLOTS, slot_probabilities


async def _seed_odds_and_user(session, balance=100_000) -> User:
    probs = slot_probabilities()
    for pos, name, mult in SLOTS:
        session.add(OddsSlot(position=pos, name=name, multiplier=mult,
                             probability=round(probs[pos], 10), is_active=True))
    user = User(email="p@example.com", display_name="Player", balance=balance)
    session.add(user)
    await session.commit()
    return user


async def _engine(test_engine, db_session, balance=100_000) -> tuple[GameEngine, User]:
    user = await _seed_odds_and_user(db_session, balance)
    eng = GameEngine(async_sessionmaker(test_engine, expire_on_commit=False))
    await eng.load_slots()
    await eng.open_round()
    return eng, user


@pytest.mark.asyncio
async def test_bet_deducts_balance_and_writes_ledger(test_engine, db_session):
    eng, user = await _engine(test_engine, db_session)
    ack = await eng.place_bet(user.id, slot_position=0, amount=1_000)
    assert ack["balance"] == 99_000
    tx = await db_session.scalar(select(Transaction).where(Transaction.user_id == user.id))
    assert tx.type == "bet" and tx.amount == -1_000 and tx.balance_after == 99_000


@pytest.mark.asyncio
async def test_bet_rejections(test_engine, db_session):
    eng, user = await _engine(test_engine, db_session, balance=500)
    with pytest.raises(BetError, match="Insufficient"):
        await eng.place_bet(user.id, 0, 1_000)
    with pytest.raises(BetError, match="chip"):
        await eng.place_bet(user.id, 0, 123)  # not a chip value
    with pytest.raises(BetError, match="slot"):
        await eng.place_bet(user.id, 99, 200)
    eng.state.phase = "SPINNING"
    with pytest.raises(BetError, match="closed"):
        await eng.place_bet(user.id, 0, 200)


@pytest.mark.asyncio
async def test_stacked_and_multi_slot_bets_allowed(test_engine, db_session):
    eng, user = await _engine(test_engine, db_session)
    await eng.place_bet(user.id, 0, 200)
    await eng.place_bet(user.id, 0, 200)   # stack same slot
    ack = await eng.place_bet(user.id, 5, 1_000)  # different slot
    assert ack["balance"] == 100_000 - 400 - 1_000
    bets = (await db_session.scalars(select(Bet))).all()
    assert len(bets) == 3


@pytest.mark.asyncio
async def test_settle_pays_winners_and_reveals_seed(test_engine, db_session):
    eng, user = await _engine(test_engine, db_session)
    # Bet on every slot so exactly one bet must win.
    for pos in range(8):
        await eng.place_bet(user.id, pos, 1_000)
    result = await eng.settle_round()

    assert result["type"] == "spin_result"
    win_pos, mult = result["winning_position"], result["multiplier"]
    assert rng.commitment(result["server_seed"], result["round_id"]) == result["commit"]

    rnd = await db_session.get(Round, result["round_id"])
    assert rnd.server_seed == result["server_seed"]
    assert rnd.winning_position == win_pos

    await db_session.refresh(user)
    assert user.balance == 100_000 - 8_000 + (mult + 1) * 1_000
    assert result["top3"][0]["user_id"] == user.id

    win_tx = await db_session.scalar(
        select(Transaction).where(Transaction.type == "win", Transaction.user_id == user.id)
    )
    assert win_tx.amount == (mult + 1) * 1_000


@pytest.mark.asyncio
async def test_full_round_broadcasts(test_engine, db_session, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "betting_seconds", 1)
    monkeypatch.setattr(s, "spinning_seconds", 1)
    monkeypatch.setattr(s, "results_seconds", 1)

    eng, user = await _engine(test_engine, db_session)
    received: list[dict] = []

    async def collect(msg):
        received.append(msg)

    eng.subscribe(collect)
    await eng.run_one_round()

    phases = [m["phase"] for m in received if m["type"] == "round_state"]
    assert BETTING in phases and "SPINNING" in phases and "RESULTS" in phases
    assert any(m["type"] == "spin_result" for m in received)
