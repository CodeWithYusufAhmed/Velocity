"""Public provably-fair verification endpoints — no auth required on purpose:
anyone, even without an account, can audit any past round."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.game import rng
from app.models import OddsSlot, Round

router = APIRouter(prefix="/rounds", tags=["rounds"])


@router.get("/odds")
async def live_odds(session: AsyncSession = Depends(get_session)) -> list[dict]:
    """The live odds table — shown in the app's About screen."""
    rows = (
        await session.scalars(
            select(OddsSlot).where(OddsSlot.is_active).order_by(OddsSlot.position)
        )
    ).all()
    return [
        {
            "position": r.position, "name": r.name, "multiplier": r.multiplier,
            "probability": float(r.probability),
            "rtp": float(Decimal(r.probability) * (r.multiplier + 1)),
        }
        for r in rows
    ]


@router.get("/{round_id}/verify")
async def verify_round(round_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    rnd = await session.get(Round, round_id)
    if rnd is None:
        raise HTTPException(404, "Round not found")
    if rnd.server_seed is None:
        return {"round_id": rnd.id, "commit": rnd.commit, "revealed": False}

    slots = (
        await session.scalars(
            select(OddsSlot).where(OddsSlot.is_active).order_by(OddsSlot.position)
        )
    ).all()
    probs = [Decimal(s.probability) for s in slots]
    recomputed_commit = rng.commitment(rnd.server_seed, rnd.id)
    recomputed_winner = slots[rng.select_slot(rnd.server_seed, rnd.id, probs)].position
    return {
        "round_id": rnd.id,
        "revealed": True,
        "commit": rnd.commit,
        "server_seed": rnd.server_seed,
        "winning_position": rnd.winning_position,
        "recomputed_commit": recomputed_commit,
        "recomputed_winning_position": recomputed_winner,
        "commit_valid": recomputed_commit == rnd.commit,
        "result_valid": recomputed_winner == rnd.winning_position,
        "how_to_verify": (
            "commit = SHA256(server_seed || round_id); "
            "winner = weighted pick using HMAC-SHA256(server_seed, round_id) "
            "mapped onto the public odds table (GET /rounds/odds)"
        ),
    }
