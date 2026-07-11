from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import FriendRequest, User
from app.rate_limit import limiter
from app.services import friends as svc, vip
from app.services.friends import FriendError
from app.ws.social import social_hub

router = APIRouter(prefix="/friends", tags=["friends"])


class RequestBody(BaseModel):
    user_id: int


def _err(e: FriendError):
    raise HTTPException(e.status_code, str(e))


@router.get("")
async def list_friends(user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    ids = await svc.friend_ids(session, user.id)
    users = (await session.scalars(select(User).where(User.id.in_(ids)))).all() if ids else []
    tier = await vip.active_tier(session, user.id)
    return {
        "friend_limit": vip.friend_limit(tier),
        "count": len(users),
        "friends": [
            {"id": u.id, "display_name": u.display_name,
             "online": social_hub.is_online(u.id),
             "vip_tier": await vip.active_tier(session, u.id)}
            for u in users
        ],
    }


@router.get("/requests")
async def list_requests(user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(FriendRequest).where(
        FriendRequest.status == "pending",
        or_(FriendRequest.recipient_id == user.id, FriendRequest.sender_id == user.id)))).all()
    names = {}
    for fr in rows:
        for uid in (fr.sender_id, fr.recipient_id):
            if uid not in names:
                names[uid] = (await session.get(User, uid)).display_name
    return [
        {"id": fr.id, "sender_id": fr.sender_id, "recipient_id": fr.recipient_id,
         "sender_name": names[fr.sender_id], "recipient_name": names[fr.recipient_id],
         "incoming": fr.recipient_id == user.id}
        for fr in rows
    ]


@router.post("/requests", status_code=201)
@limiter.limit("20/hour")
async def send_request(request: Request, body: RequestBody,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    try:
        fr = await svc.send_request(session, user.id, body.user_id)
    except FriendError as e:
        _err(e)
    await social_hub.send_to(body.user_id, {
        "type": "friend_request", "request_id": fr.id,
        "sender_id": user.id, "sender_name": user.display_name})
    return {"request_id": fr.id}


@router.post("/requests/{request_id}/accept", status_code=204)
async def accept(request_id: int, user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(get_session)):
    try:
        await svc.accept(session, request_id, user.id)
    except FriendError as e:
        _err(e)
    fr = await session.get(FriendRequest, request_id)
    await social_hub.send_to(fr.sender_id, {
        "type": "friend_accepted", "user_id": user.id, "display_name": user.display_name})


@router.post("/requests/{request_id}/decline", status_code=204)
async def decline(request_id: int, user: User = Depends(get_current_user),
                  session: AsyncSession = Depends(get_session)):
    try:
        await svc.decline(session, request_id, user.id)
    except FriendError as e:
        _err(e)


@router.delete("/requests/{request_id}", status_code=204)
async def cancel(request_id: int, user: User = Depends(get_current_user),
                 session: AsyncSession = Depends(get_session)):
    try:
        await svc.cancel(session, request_id, user.id)
    except FriendError as e:
        _err(e)


@router.delete("/{other_id}", status_code=204)
async def unfriend(other_id: int, user: User = Depends(get_current_user),
                   session: AsyncSession = Depends(get_session)):
    await svc.unfriend(session, user.id, other_id)


@router.get("/search")
async def search_users(q: str, user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    q = q.strip()
    if len(q) < 2:
        return []
    rows = (await session.scalars(select(User).where(
        User.display_name.ilike(f"%{q}%"), User.id != user.id,
        User.is_banned.is_(False)).limit(20))).all()
    return [{"id": u.id, "display_name": u.display_name,
             "vip_tier": await vip.active_tier(session, u.id)} for u in rows]
