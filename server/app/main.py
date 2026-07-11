"""Velocity server entry point."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import SessionLocal
from app.game.engine import GameEngine
from app.rate_limit import limiter
from app.routers import auth, economy, rounds, tables
from app.ws import game as ws_game
from app.ws import social as ws_social


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine_task = None
    if get_settings().round_engine_enabled:
        engine = GameEngine(SessionLocal)
        engine.subscribe(ws_game.hub.broadcast)
        app.state.engine = engine
        engine_task = asyncio.create_task(engine.run_forever())
    yield
    if engine_task:
        app.state.engine.stop()
        engine_task.cancel()


app = FastAPI(
    title="Velocity",
    description=(
        "Free multiplayer wheel game + social voice platform. "
        "Virtual coins only — nothing of monetary value can be wagered or won."
    ),
    version="0.0.3",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth.router)
app.include_router(economy.router)
app.include_router(rounds.router)
app.include_router(tables.router)
app.include_router(tables.safety_router)
app.include_router(ws_game.router)
app.include_router(ws_social.router)


@app.get("/health")
async def health() -> dict:
    """Liveness probe used by deploy tooling and the Android app's connectivity check."""
    return {"status": "ok", "service": "velocity", "version": app.version}
