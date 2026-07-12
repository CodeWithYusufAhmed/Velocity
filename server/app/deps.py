"""Common FastAPI dependencies."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise HTTPException(401, "Not authenticated")
    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise HTTPException(401, "Invalid or expired token")
    user = await session.get(User, user_id)
    if user is None or user.is_banned:
        raise HTTPException(401, "Invalid or expired token")
    if user.banned_until is not None:
        from datetime import datetime, timezone
        if user.banned_until > datetime.now(timezone.utc):
            mins = int((user.banned_until - datetime.now(timezone.utc)).total_seconds() // 60) + 1
            raise HTTPException(403, f"You are temporarily banned ({mins} min left)")
    return user
