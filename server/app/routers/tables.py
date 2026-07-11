from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import Table, User
from app.rate_limit import limiter
from app.services import safety, tables as svc
from app.services.safety import SafetyError
from app.services.tables import TableError
from app.ws.social import notify_table

router = APIRouter(prefix="/tables", tags=["tables"])


class CreateTableRequest(BaseModel):
    name: str = Field(min_length=2, max_length=48)
    topic: str | None = Field(default=None, max_length=120)
    chair_count: int


class TargetRequest(BaseModel):
    user_id: int


class SitRequest(BaseModel):
    position: int


class ReportRequest(BaseModel):
    user_id: int
    reason: str = Field(min_length=2, max_length=40)
    note: str | None = Field(default=None, max_length=500)
    table_id: int | None = None


def _err(e: Exception, code: int):
    raise HTTPException(code, str(e))


@router.post("", status_code=201)
@limiter.limit("5/hour")
async def create_table(request: Request, body: CreateTableRequest,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    try:
        t = await svc.create_table(session, user, body.name, body.topic, body.chair_count)
    except TableError as e:
        _err(e, e.status_code)
    return {"id": t.id, "name": t.name, "topic": t.topic, "chair_count": t.chair_count}


@router.get("")
async def list_tables(session: AsyncSession = Depends(get_session),
                      user: User = Depends(get_current_user)):
    rows = (await session.scalars(select(Table).where(Table.status == "open")
                                  .order_by(Table.created_at.desc()))).all()
    out = []
    for t in rows:
        room = svc.hub.room(t.id)
        out.append({
            "id": t.id, "name": t.name, "topic": t.topic, "chair_count": t.chair_count,
            "member_count": len(room.members) if room else 0,
            "speakers": len(room.chairs) if room else 0,
        })
    return out


@router.post("/{table_id}/join")
async def join(table_id: int, user: User = Depends(get_current_user),
               session: AsyncSession = Depends(get_session)):
    try:
        result = await svc.join_table(session, table_id, user)
    except TableError as e:
        _err(e, e.status_code)
    await notify_table(table_id, {"type": "table_event", "event": "join",
                                  "table_id": table_id, "user_id": user.id,
                                  "display_name": user.display_name,
                                  "vip_tier": result["vip_tier"]})
    return result


@router.post("/{table_id}/leave", status_code=204)
async def leave(table_id: int, user: User = Depends(get_current_user)):
    svc.leave_table(table_id, user.id)
    await notify_table(table_id, {"type": "table_event", "event": "leave",
                                  "table_id": table_id, "user_id": user.id})


@router.post("/{table_id}/sit")
async def sit(table_id: int, body: SitRequest, user: User = Depends(get_current_user)):
    try:
        svc.sit(table_id, user.id, body.position)
    except TableError as e:
        _err(e, e.status_code)
    await notify_table(table_id, {"type": "table_event", "event": "sit",
                                  "table_id": table_id, "user_id": user.id,
                                  "position": body.position})
    return {"seated": body.position}


@router.post("/{table_id}/stand", status_code=204)
async def stand(table_id: int, user: User = Depends(get_current_user)):
    svc.stand(table_id, user.id)
    await notify_table(table_id, {"type": "table_event", "event": "stand",
                                  "table_id": table_id, "user_id": user.id})


def _moderation(action_name: str, coro_factory):
    async def endpoint(table_id: int, body: TargetRequest,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
        try:
            result = await coro_factory(session, table_id, user.id, body.user_id)
        except TableError as e:
            _err(e, e.status_code)
        await notify_table(table_id, {"type": "table_event", "event": action_name,
                                      "table_id": table_id, "user_id": body.user_id,
                                      "by": user.id, **result})
        return result
    return endpoint


router.post("/{table_id}/kick")(_moderation("kick", svc.kick))
router.post("/{table_id}/mute")(_moderation("mute", svc.mute))
router.post("/{table_id}/block")(_moderation("block", svc.block))
router.post("/{table_id}/chat-ban")(_moderation("chat_ban", svc.chat_ban))


@router.post("/{table_id}/admins")
async def grant_admin(table_id: int, body: TargetRequest,
                      user: User = Depends(get_current_user),
                      session: AsyncSession = Depends(get_session)):
    try:
        result = await svc.grant_admin(session, table_id, user.id, body.user_id, grant=True)
    except TableError as e:
        _err(e, e.status_code)
    await notify_table(table_id, {"type": "table_event", "event": "role",
                                  "table_id": table_id, "user_id": body.user_id, **result})
    return result


@router.delete("/{table_id}/admins/{target_id}")
async def revoke_admin(table_id: int, target_id: int,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    try:
        result = await svc.grant_admin(session, table_id, user.id, target_id, grant=False)
    except TableError as e:
        _err(e, e.status_code)
    return result


@router.delete("/{table_id}", status_code=204)
async def close(table_id: int, user: User = Depends(get_current_user),
                session: AsyncSession = Depends(get_session)):
    try:
        await svc.close_table(session, table_id, user.id)
    except TableError as e:
        _err(e, e.status_code)
    await notify_table(table_id, {"type": "table_event", "event": "closed",
                                  "table_id": table_id})


safety_router = APIRouter(tags=["safety"])


@safety_router.post("/reports", status_code=201)
@limiter.limit("10/hour")
async def report(request: Request, body: ReportRequest,
                 user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(get_session)):
    try:
        r = await safety.report_user(session, user.id, body.user_id,
                                     body.reason, body.note, body.table_id)
    except SafetyError as e:
        _err(e, e.status_code)
    return {"report_id": r.id}


@safety_router.post("/blocks/{target_id}", status_code=204)
async def block_user(target_id: int, user: User = Depends(get_current_user),
                     session: AsyncSession = Depends(get_session)):
    try:
        await safety.block_user(session, user.id, target_id)
    except SafetyError as e:
        _err(e, e.status_code)


@safety_router.delete("/blocks/{target_id}", status_code=204)
async def unblock_user(target_id: int, user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    await safety.unblock_user(session, user.id, target_id)
