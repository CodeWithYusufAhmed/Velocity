"""Profile pictures: small circular avatars (max 200 KB), stored in the users row.
Pulled forward from the later-features list at Yusuf's request (M10)."""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User

router = APIRouter(tags=["avatars"])

MAX_BYTES = 200 * 1024
ALLOWED = {"image/png", "image/jpeg", "image/webp"}


@router.post("/me/avatar", status_code=204)
async def upload_avatar(file: UploadFile, user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "Use a PNG, JPEG or WebP image")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image too large — max 200 KB (the app downscales for you)")
    db_user = await session.get(User, user.id)
    db_user.avatar, db_user.avatar_mime = data, file.content_type
    await session.commit()


@router.get("/users/{user_id}/avatar")
async def get_avatar(user_id: int, session: AsyncSession = Depends(get_session)):
    u = await session.get(User, user_id)
    if u is None or u.avatar is None:
        raise HTTPException(404, "No avatar")  # client falls back to initials
    return Response(content=u.avatar, media_type=u.avatar_mime or "image/png",
                    headers={"Cache-Control": "public, max-age=300"})
