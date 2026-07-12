"""In-app moderator endpoints (Velocity owner only). Every action is audited."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import AdminAudit, Report, Transaction, User, VipStatus
from app.services.vip import TIERS

router = APIRouter(prefix="/mod", tags=["moderator"])


async def require_moderator(user: User = Depends(get_current_user)) -> User:
    if not user.is_moderator:
        raise HTTPException(403, "Moderator only")
    return user


def _audit(session: AsyncSession, mod: User, action: str, target: int, detail: str = ""):
    session.add(AdminAudit(admin_id=mod.id, action=f"mod_{action}",
                           target_user_id=target, detail=detail))


class GiftVipRequest(BaseModel):
    user_id: int
    tier: int = Field(ge=1, le=5)


class GiftCoinsRequest(BaseModel):
    user_id: int
    amount: int = Field(gt=0, le=1_000_000_000)


class BanRequest(BaseModel):
    user_id: int
    minutes: int | None = Field(default=None, ge=1)  # None = permanent


@router.post("/gift-vip")
async def gift_vip(body: GiftVipRequest, mod: User = Depends(require_moderator),
                   session: AsyncSession = Depends(get_session)):
    target = await session.get(User, body.user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    now = datetime.now(timezone.utc)
    _, days = TIERS[body.tier]
    status = await session.get(VipStatus, body.user_id)
    if status is None:
        session.add(VipStatus(user_id=body.user_id, tier=body.tier,
                              awarded_at=now, expires_at=now + timedelta(days=days)))
    else:
        status.tier, status.awarded_at, status.expires_at = body.tier, now, now + timedelta(days=days)
    _audit(session, mod, "gift_vip", body.user_id, f"VIP{body.tier}")
    await session.commit()
    return {"gifted": f"VIP{body.tier}", "days": days}


@router.post("/gift-coins")
async def gift_coins(body: GiftCoinsRequest, mod: User = Depends(require_moderator),
                     session: AsyncSession = Depends(get_session)):
    target = await session.get(User, body.user_id, with_for_update=True)
    if target is None:
        raise HTTPException(404, "User not found")
    target.balance += body.amount
    session.add(Transaction(user_id=target.id, type="admin_adjust", amount=body.amount,
                            balance_after=target.balance, note="moderator gift"))
    _audit(session, mod, "gift_coins", body.user_id, f"+{body.amount}")
    await session.commit()
    return {"balance": target.balance}


@router.post("/ban")
async def ban(body: BanRequest, mod: User = Depends(require_moderator),
              session: AsyncSession = Depends(get_session)):
    target = await session.get(User, body.user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if target.is_moderator:
        raise HTTPException(400, "Cannot ban a moderator")
    if body.minutes is None:
        target.is_banned, target.banned_until = True, None
        detail = "permanent"
    else:
        target.banned_until = datetime.now(timezone.utc) + timedelta(minutes=body.minutes)
        detail = f"{body.minutes} min"
    _audit(session, mod, "ban", body.user_id, detail)
    await session.commit()
    return {"banned": detail}


@router.post("/unban/{user_id}")
async def unban(user_id: int, mod: User = Depends(require_moderator),
                session: AsyncSession = Depends(get_session)):
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    target.is_banned, target.banned_until = False, None
    _audit(session, mod, "unban", user_id)
    await session.commit()
    return {"unbanned": True}


@router.get("/reports")
async def reports(mod: User = Depends(require_moderator),
                  session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(Report).where(Report.status == "open")
                                  .order_by(Report.created_at))).all()
    out = []
    for r in rows:
        reporter = await session.get(User, r.reporter_id)
        reported = await session.get(User, r.reported_id)
        out.append({"id": r.id, "reporter": reporter.display_name if reporter else "?",
                    "reported": reported.display_name if reported else "?",
                    "reported_id": r.reported_id, "reason": r.reason, "note": r.note})
    return out


@router.post("/reports/{report_id}/resolve", status_code=204)
async def resolve(report_id: int, mod: User = Depends(require_moderator),
                  session: AsyncSession = Depends(get_session)):
    r = await session.get(Report, report_id)
    if r and r.status == "open":
        r.status, r.resolved_by, r.resolved_at = "resolved", mod.id, datetime.now(timezone.utc)
        _audit(session, mod, "resolve_report", r.reported_id, f"report {r.id}")
        await session.commit()
