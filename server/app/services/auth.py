"""Auth flows: register, login, Google sign-in, refresh rotation, logout.

Refresh rotation policy: each refresh token is single-use. Using it revokes it
and issues a successor. Reusing an already-rotated token is treated as theft:
every active session for that user is revoked (industry-standard reuse detection).
"""

from datetime import datetime, timedelta, timezone

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Credential, RefreshToken, User
from app.schemas.auth import AuthResponse, TokenPair, UserOut
from app.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)


class AuthError(Exception):
    """Raised with a safe, user-facing message."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


async def _issue_tokens(session: AsyncSession, user: User) -> TokenPair:
    s = get_settings()
    raw = new_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(days=s.jwt_refresh_ttl_days),
        )
    )
    await session.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=raw)


def _auth_response(user: User, tokens: TokenPair) -> AuthResponse:
    return AuthResponse(
        user=UserOut(id=user.id, email=user.email, display_name=user.display_name, balance=user.balance),
        tokens=tokens,
    )


async def register(session: AsyncSession, email: str, display_name: str, password: str) -> AuthResponse:
    email = email.lower().strip()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise AuthError("An account with this email already exists", 409)
    user = User(email=email, display_name=display_name.strip(), balance=0)
    session.add(user)
    await session.flush()
    session.add(Credential(user_id=user.id, password_hash=hash_password(password)))
    await session.commit()
    return _auth_response(user, await _issue_tokens(session, user))


async def login(session: AsyncSession, email: str, password: str) -> AuthResponse:
    user = await session.scalar(select(User).where(User.email == email.lower().strip()))
    cred = (
        await session.scalar(select(Credential).where(Credential.user_id == user.id))
        if user
        else None
    )
    # Same error for wrong email and wrong password — no account enumeration.
    if not user or not cred or not verify_password(cred.password_hash, password):
        raise AuthError("Invalid email or password")
    if user.is_banned:
        raise AuthError("This account is banned", 403)
    return _auth_response(user, await _issue_tokens(session, user))


async def google_login(session: AsyncSession, token: str) -> AuthResponse:
    s = get_settings()
    try:
        info = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), s.google_oauth_client_id
        )
    except ValueError:
        raise AuthError("Invalid Google token")
    sub, email = info.get("sub"), (info.get("email") or "").lower()
    if not sub or not email:
        raise AuthError("Google token missing required claims")

    user = await session.scalar(select(User).where(User.google_sub == sub))
    if not user:
        # Link by verified email if the account already exists, else create one.
        user = await session.scalar(select(User).where(User.email == email))
        if user:
            user.google_sub = sub
        else:
            user = User(
                email=email,
                display_name=(info.get("name") or email.split("@")[0])[:32],
                google_sub=sub,
                balance=0,
            )
            session.add(user)
        await session.commit()
    if user.is_banned:
        raise AuthError("This account is banned", 403)
    return _auth_response(user, await _issue_tokens(session, user))


async def refresh(session: AsyncSession, raw_token: str) -> TokenPair:
    now = datetime.now(timezone.utc)
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if not row or row.expires_at < now:
        raise AuthError("Invalid refresh token")
    if row.revoked_at is not None:
        # Reuse of a rotated token → assume theft, kill all sessions.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await session.commit()
        raise AuthError("Invalid refresh token")

    user = await session.get(User, row.user_id)
    if not user or user.is_banned:
        raise AuthError("Invalid refresh token")

    s = get_settings()
    new_raw = new_refresh_token()
    successor = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw),
        expires_at=now + timedelta(days=s.jwt_refresh_ttl_days),
    )
    session.add(successor)
    await session.flush()
    row.revoked_at = now
    row.replaced_by_id = successor.id
    await session.commit()
    return TokenPair(access_token=create_access_token(user.id), refresh_token=new_raw)


async def logout(session: AsyncSession, raw_token: str) -> None:
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await session.commit()
