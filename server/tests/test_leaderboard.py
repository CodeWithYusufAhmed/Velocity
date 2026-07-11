"""Leaderboards, recent-rounds strip, My Record."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.game.engine import GameEngine
from app.models import DailyStats, Round, User
from app.services.economy import game_today
from tests.test_engine import _seed_odds_and_user


async def _auth_headers(client, email="lb@example.com", name="LB"):
    r = await client.post("/auth/register", json={
        "email": email, "display_name": name, "password": "s3cretpass"})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}, r.json()["user"]["id"]


@pytest.mark.asyncio
async def test_daily_top10_orders_by_net(client, db_session):
    headers, my_id = await _auth_headers(client)
    others = [User(email=f"o{i}@x.com", display_name=f"O{i}", balance=0) for i in range(12)]
    db_session.add_all(others)
    await db_session.flush()
    today = game_today()
    for i, u in enumerate(others):
        db_session.add(DailyStats(user_id=u.id, day=today,
                                  total_won=(i + 1) * 1_000, total_bet=500))
    await db_session.commit()

    r = await client.get("/leaderboard/daily", headers=headers)
    board = r.json()
    assert len(board) == 10
    assert board[0]["net_winnings"] == 12_000 - 500
    assert [row["rank"] for row in board] == list(range(1, 11))
    nets = [row["net_winnings"] for row in board]
    assert nets == sorted(nets, reverse=True)


@pytest.mark.asyncio
async def test_recent_rounds_strip_and_top3_stored(client, test_engine, db_session):
    user = await _seed_odds_and_user(db_session)
    eng = GameEngine(async_sessionmaker(test_engine, expire_on_commit=False))
    await eng.load_slots()
    for _ in range(3):
        await eng.open_round()
        for pos in range(8):          # cover every slot → guaranteed one win
            await eng.place_bet(user.id, pos, 200)
        await eng.settle_round()

    r = await client.get("/rounds/recent?limit=2")
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["round_id"] > rows[1]["round_id"]        # newest first
    assert all("name" in row and "multiplier" in row for row in rows)

    # Top 3 persisted on the round row when the user won.
    winners = (await db_session.scalars(
        select(Round).where(Round.resulted_at.is_not(None)))).all()
    assert len(winners) == 3
    for w in winners:
        assert w.top3 and w.top3[0]["user_id"] == user.id


@pytest.mark.asyncio
async def test_my_record_aggregates(client, db_session):
    headers, my_id = await _auth_headers(client, "rec@example.com", "Rec")
    from datetime import timedelta
    today = game_today()
    db_session.add_all([
        DailyStats(user_id=my_id, day=today - timedelta(days=1),
                   rounds_played=10, total_bet=5_000, total_won=9_000, biggest_win=6_000),
        DailyStats(user_id=my_id, day=today,
                   rounds_played=5, total_bet=2_000, total_won=1_000, biggest_win=1_000),
    ])
    await db_session.commit()

    r = await client.get("/me/record", headers=headers)
    rec = r.json()
    assert rec["rounds_played"] == 15
    assert rec["net_total"] == 10_000 - 7_000
    assert rec["biggest_win"] == 6_000
    assert rec["money_not_spent"]["free_coins_received"] == 100_000  # signup grant
