"""Velocity server entry point.

M0: boots FastAPI and answers /health. Routers, DB, and WebSockets arrive in
later milestones.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Velocity",
    description=(
        "Free multiplayer wheel game + social voice platform. "
        "Virtual coins only — nothing of monetary value can be wagered or won."
    ),
    version="0.0.1",
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe used by deploy tooling and the Android app's connectivity check."""
    return {"status": "ok", "service": "velocity", "version": app.version}
