"""Velocity server entry point."""

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.rate_limit import limiter
from app.routers import auth

app = FastAPI(
    title="Velocity",
    description=(
        "Free multiplayer wheel game + social voice platform. "
        "Virtual coins only — nothing of monetary value can be wagered or won."
    ),
    version="0.0.2",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth.router)


@app.get("/health")
async def health() -> dict:
    """Liveness probe used by deploy tooling and the Android app's connectivity check."""
    return {"status": "ok", "service": "velocity", "version": app.version}
