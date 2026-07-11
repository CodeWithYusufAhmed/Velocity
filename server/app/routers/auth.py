from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.rate_limit import limiter
from app.schemas.auth import (
    AuthResponse,
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.services import auth as auth_service
from app.services.auth import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def _raise(e: AuthError) -> None:
    raise HTTPException(status_code=e.status_code, detail=str(e))


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("3/hour")
async def register(request: Request, body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await auth_service.register(session, body.email, body.display_name, body.password)
    except AuthError as e:
        _raise(e)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await auth_service.login(session, body.email, body.password)
    except AuthError as e:
        _raise(e)


@router.post("/google", response_model=AuthResponse)
@limiter.limit("10/minute")
async def google(request: Request, body: GoogleLoginRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await auth_service.google_login(session, body.id_token)
    except AuthError as e:
        _raise(e)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(request: Request, body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    try:
        return await auth_service.refresh(session, body.refresh_token)
    except AuthError as e:
        _raise(e)


@router.post("/logout", status_code=204)
async def logout(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    await auth_service.logout(session, body.refresh_token)
