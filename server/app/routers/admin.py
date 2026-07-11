"""Admin dashboard (/admin) — server-rendered Jinja2, Yusuf only.

Access requires BOTH: an account with is_admin=True (log in with its email)
AND the separate ADMIN_PASSWORD from server/.env. A signed 12h cookie holds
the session. Every mutating action writes an admin_audit row.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import (AdminAudit, Bet, DailyStats, OddsSlot, Report, Round,
                        RuntimeSetting, Table, Transaction, User, VipStatus)
from app.security import verify_password
from app.services import tables as tables_svc
from app.services.economy import game_today

router = APIRouter(prefix="/admin", include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[3] / "admin" / "templates"))

COOKIE = "velocity_admin"


def _make_cookie(user_id: int) -> str:
    s = get_settings()
    return jwt.encode({"admin": True, "sub": str(user_id),
                       "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
                      s.jwt_secret, algorithm="HS256")


async def require_admin(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE, "")
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        assert payload.get("admin") is True
    except Exception:
        raise HTTPException(status_code=307, headers={"Location": "/admin/login"})
    user = await session.get(User, int(payload["sub"]))
    if user is None or not user.is_admin:
        raise HTTPException(status_code=307, headers={"Location": "/admin/login"})
    return user


async def _audit(session: AsyncSession, admin: User, action: str,
                 target: int | None = None, detail: str = "") -> None:
    session.add(AdminAudit(admin_id=admin.id, action=action,
                           target_user_id=target, detail=detail))


# ---- auth ------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = Form(), password: str = Form(),
                admin_password: str = Form(), session: AsyncSession = Depends(get_session)):
    from app.models import Credential
    s = get_settings()
    user = await session.scalar(select(User).where(User.email == email.lower().strip()))
    cred = await session.scalar(select(Credential).where(Credential.user_id == user.id)) if user else None
    ok = (
        s.admin_password
        and user is not None and user.is_admin
        and cred is not None and verify_password(cred.password_hash, password)
        and admin_password == s.admin_password
    )
    if not ok:
        return templates.TemplateResponse(request, "login.html",
                                          {"error": "Invalid credentials"}, status_code=401)
    resp = RedirectResponse("/admin", status_code=303)
    resp.set_cookie(COOKIE, _make_cookie(user.id), httponly=True, samesite="lax", max_age=43200)
    return resp


# ---- dashboard -------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, q: str = "",
                    admin: User = Depends(require_admin),
                    session: AsyncSession = Depends(get_session)):
    today = game_today()
    engine = getattr(request.app.state, "engine", None)
    from app.ws.game import hub as game_hub
    from app.ws.social import social_hub

    coin_supply = await session.scalar(select(func.coalesce(func.sum(User.balance), 0)))
    user_count = await session.scalar(select(func.count()).select_from(User))
    rounds_today = await session.scalar(
        select(func.count()).select_from(Round).where(
            Round.resulted_at.is_not(None),
            Round.betting_opened_at >= datetime.now(timezone.utc) - timedelta(days=1)))

    biggest = (await session.execute(
        select(User.display_name, DailyStats.biggest_win)
        .join(User, User.id == DailyStats.user_id)
        .where(DailyStats.day == today)
        .order_by(DailyStats.biggest_win.desc()).limit(5))).all()

    users = []
    if q:
        users = (await session.scalars(select(User).where(
            User.display_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")).limit(20))).all()

    odds = (await session.scalars(select(OddsSlot).order_by(OddsSlot.position))).all()
    rtps = [float(Decimal(o.probability) * (o.multiplier + 1)) for o in odds]
    rtp_uniform = max(rtps) - min(rtps) < 1e-6 if rtps else True
    prob_sum = float(sum(Decimal(o.probability) for o in odds))

    open_tables = (await session.scalars(select(Table).where(Table.status == "open"))).all()
    tables_view = [{"t": t, "room": tables_svc.hub.room(t.id)} for t in open_tables]

    reports = (await session.scalars(select(Report).where(Report.status == "open")
                                     .order_by(Report.created_at))).all()
    vips = (await session.execute(
        select(User.display_name, VipStatus.tier, VipStatus.expires_at)
        .join(User, User.id == VipStatus.user_id)
        .where(VipStatus.expires_at > datetime.now(timezone.utc))
        .order_by(VipStatus.tier.desc()))).all()

    caps = {r.key: r.value for r in (await session.scalars(select(RuntimeSetting))).all()}
    s = get_settings()

    return templates.TemplateResponse(request, "dashboard.html", {
        "admin": admin, "q": q, "users": users,
        "engine_state": getattr(engine, "state", None),
        "online_game": len(game_hub.sockets), "online_social": len(social_hub.by_user),
        "coin_supply": coin_supply, "user_count": user_count, "rounds_today": rounds_today,
        "biggest": biggest, "odds": odds, "rtps": rtps,
        "rtp_uniform": rtp_uniform, "prob_sum": prob_sum,
        "tables": tables_view, "reports": reports, "vips": vips,
        "max_tables": caps.get("max_tables", s.max_tables),
        "max_listeners": caps.get("max_listeners_per_table", s.max_listeners_per_table),
    })


# ---- actions ----------------------------------------------------------------

@router.post("/users/{user_id}/adjust")
async def adjust_balance(user_id: int, amount: int = Form(), note: str = Form(""),
                         admin: User = Depends(require_admin),
                         session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise HTTPException(404)
    if user.balance + amount < 0:
        amount = -user.balance  # never drive a balance negative
    user.balance += amount
    session.add(Transaction(user_id=user.id, type="admin_adjust", amount=amount,
                            balance_after=user.balance, note=note or None))
    await _audit(session, admin, "adjust_balance", user.id, f"{amount:+} ({note})")
    await session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/users/{user_id}/ban")
async def ban(user_id: int, banned: bool = Form(),
              admin: User = Depends(require_admin),
              session: AsyncSession = Depends(get_session)):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(404)
    user.is_banned = banned
    await _audit(session, admin, "ban" if banned else "unban", user.id)
    await session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/odds/{position}")
async def edit_odds(position: int, multiplier: int = Form(), probability: str = Form(),
                    name: str = Form(), admin: User = Depends(require_admin),
                    session: AsyncSession = Depends(get_session)):
    slot = await session.scalar(select(OddsSlot).where(OddsSlot.position == position))
    if slot is None:
        raise HTTPException(404)
    slot.name, slot.multiplier, slot.probability = name.strip(), multiplier, Decimal(probability)
    await _audit(session, admin, "edit_odds", detail=f"pos {position}: {name} x{multiplier} p={probability}")
    await session.commit()
    # The engine reloads slots at next round start via load_slots (M13 hardening:
    # it currently loads once at startup — restart applies edits; noted on the page).
    return RedirectResponse("/admin", status_code=303)


@router.post("/tables/{table_id}/close")
async def force_close(table_id: int, admin: User = Depends(require_admin),
                      session: AsyncSession = Depends(get_session)):
    t = await session.get(Table, table_id)
    if t and t.status == "open":
        t.status, t.closed_at = "closed", datetime.now(timezone.utc)
        tables_svc.hub.rooms.pop(table_id, None)
        await _audit(session, admin, "force_close_table", detail=f"table {table_id} ({t.name})")
        await session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/reports/{report_id}/resolve")
async def resolve_report(report_id: int, admin: User = Depends(require_admin),
                         session: AsyncSession = Depends(get_session)):
    r = await session.get(Report, report_id)
    if r and r.status == "open":
        r.status, r.resolved_by, r.resolved_at = "resolved", admin.id, datetime.now(timezone.utc)
        await _audit(session, admin, "resolve_report", r.reported_id, f"report {r.id}")
        await session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/capacity")
async def capacity(max_tables: int = Form(), max_listeners: int = Form(),
                   admin: User = Depends(require_admin),
                   session: AsyncSession = Depends(get_session)):
    for key, val in (("max_tables", max_tables), ("max_listeners_per_table", max_listeners)):
        row = await session.get(RuntimeSetting, key)
        if row:
            row.value = str(val)
        else:
            session.add(RuntimeSetting(key=key, value=str(val)))
    await _audit(session, admin, "capacity", detail=f"tables={max_tables} listeners={max_listeners}")
    await session.commit()
    return RedirectResponse("/admin", status_code=303)
