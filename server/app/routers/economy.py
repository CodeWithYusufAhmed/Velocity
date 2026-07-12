"""Economy + profile endpoints (all authenticated)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.services import economy, vip
from app.services.economy import EconomyError

router = APIRouter(prefix="/me", tags=["economy"])


class RoundLimitRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=10_000)  # None = off


@router.get("")
async def profile(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    stats = await economy.get_daily_stats(session, user.id)
    tier = await vip.active_tier(session, user.id)
    mns = await economy.money_not_spent(session, user.id)
    limit = await economy.effective_round_limit(session, user.id)
    await session.commit()  # persists lazily-created rows / resolved pending limit
    return {
        "id": user.id, "email": user.email, "display_name": user.display_name,
        "balance": user.balance,
        "is_moderator": user.is_moderator,
        "vip_tier": tier,
        "money_not_spent": mns,
        "today": {
            "rounds_played": stats.rounds_played, "total_bet": stats.total_bet,
            "total_won": stats.total_won, "biggest_win": stats.biggest_win,
            "bonus_claimed": stats.bonus_claimed, "rescues_used": stats.rescues_used,
        },
        "daily_round_limit": limit,
    }


@router.post("/bonus")
async def claim_bonus(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    try:
        balance = await economy.claim_daily_bonus(session, user)
    except EconomyError as e:
        raise HTTPException(e.status_code, str(e))
    return {"balance": balance, "granted": True}


@router.post("/rescue")
async def claim_rescue(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    try:
        balance = await economy.claim_rescue(session, user)
    except EconomyError as e:
        raise HTTPException(e.status_code, str(e))
    return {"balance": balance, "granted": True}


@router.put("/round-limit")
async def set_round_limit(
    body: RoundLimitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        us = await economy.set_round_limit(session, user.id, body.limit)
    except EconomyError as e:
        raise HTTPException(e.status_code, str(e))
    return {
        "daily_round_limit": us.daily_round_limit,
        "pending_round_limit": us.pending_round_limit,
        "pending_effective_date": (
            us.pending_limit_effective_date.isoformat() if us.pending_limit_effective_date else None
        ),
    }
