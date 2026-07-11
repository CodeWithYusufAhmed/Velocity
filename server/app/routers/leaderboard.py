"""Leaderboards, round history, and My Record (spec A6)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import DailyStats, OddsSlot, Round, User
from app.services import economy, vip

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard/daily")
async def daily_top10(session: AsyncSession = Depends(get_session),
                      user: User = Depends(get_current_user)):
    """Top 10 by NET winnings today (Asia/Dhaka day). Initials avatars are
    derived client-side from display_name (profile pictures: coming soon)."""
    net = (DailyStats.total_won - DailyStats.total_bet).label("net")
    rows = (await session.execute(
        select(User.id, User.display_name, net)
        .join(User, User.id == DailyStats.user_id)
        .where(DailyStats.day == economy.game_today(), User.is_banned.is_(False))
        .order_by(net.desc())
        .limit(10))).all()
    return [
        {"rank": i + 1, "user_id": uid, "display_name": name, "net_winnings": int(n),
         "vip_tier": await vip.active_tier(session, uid)}
        for i, (uid, name, n) in enumerate(rows)
    ]


@router.get("/rounds/recent")
async def recent_rounds(limit: int = Query(default=50, ge=1, le=50),
                        session: AsyncSession = Depends(get_session)):
    """The result strip: last N settled rounds, newest first. Public."""
    slots = {s.position: s for s in (await session.scalars(select(OddsSlot))).all()}
    rows = (await session.scalars(
        select(Round).where(Round.resulted_at.is_not(None))
        .order_by(Round.id.desc()).limit(limit))).all()
    return [
        {"round_id": r.id, "winning_position": r.winning_position,
         "name": slots[r.winning_position].name if r.winning_position in slots else "?",
         "multiplier": slots[r.winning_position].multiplier if r.winning_position in slots else 0,
         "top3": r.top3 or []}
        for r in rows
    ]


@router.get("/me/record")
async def my_record(user: User = Depends(get_current_user),
                    session: AsyncSession = Depends(get_session)):
    """Lifetime stats, aggregated from daily_stats (one row per active day)."""
    totals = (await session.execute(
        select(
            func.coalesce(func.sum(DailyStats.rounds_played), 0),
            func.coalesce(func.sum(DailyStats.total_bet), 0),
            func.coalesce(func.sum(DailyStats.total_won), 0),
            func.coalesce(func.max(DailyStats.biggest_win), 0),
        ).where(DailyStats.user_id == user.id))).one()
    rounds_played, total_bet, total_won, biggest_win = (int(x) for x in totals)
    return {
        "rounds_played": rounds_played,
        "total_bet": total_bet,
        "total_won": total_won,
        "net_total": total_won - total_bet,
        "biggest_win": biggest_win,
        "money_not_spent": await economy.money_not_spent(session, user.id),
    }
