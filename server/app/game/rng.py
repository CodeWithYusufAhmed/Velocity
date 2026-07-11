"""Provably fair RNG (commit-reveal).

Per round:
1. Server draws a random 32-byte server_seed.
2. Before betting opens it publishes commit = SHA256(server_seed_hex || round_id).
   The seed is fixed from that moment — the server cannot steer the result.
3. Winning slot = weighted selection driven by HMAC-SHA256(server_seed, round_id):
   the first 8 bytes of the digest, read as an unsigned int, are mapped to
   u ∈ [0,1) and matched against the cumulative probability table.
4. At results the seed is revealed. Anyone can recompute both the commit and
   the winning slot — see /rounds/{id}/verify and the in-app screen.
"""

import hashlib
import hmac
import secrets
from decimal import Decimal


def new_server_seed() -> str:
    return secrets.token_hex(32)


def commitment(server_seed_hex: str, round_id: int) -> str:
    return hashlib.sha256(f"{server_seed_hex}{round_id}".encode()).hexdigest()


def roll(server_seed_hex: str, round_id: int) -> Decimal:
    """Deterministic u ∈ [0,1) from the seed and round id."""
    digest = hmac.new(
        bytes.fromhex(server_seed_hex), str(round_id).encode(), hashlib.sha256
    ).digest()
    n = int.from_bytes(digest[:8], "big")
    return Decimal(n) / Decimal(2**64)


def select_slot(server_seed_hex: str, round_id: int, probabilities: list[Decimal]) -> int:
    """Index into the (position-ordered) probability list. Weights are
    normalized here so tiny rounding in stored values can never bias play."""
    total = sum(probabilities)
    u = roll(server_seed_hex, round_id) * total
    cumulative = Decimal(0)
    for i, p in enumerate(probabilities):
        cumulative += p
        if u < cumulative:
            return i
    return len(probabilities) - 1  # guard against edge rounding
