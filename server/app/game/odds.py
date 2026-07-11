"""Canonical wheel odds — the single source of the RTP math.

A winning bet pays back stake + stake*multiplier = (m+1)*stake. For every slot
to have the SAME player-favored return-to-player r, we need:

    p_i * (m_i + 1) = r  for all i,  with  sum(p_i) = 1
    =>  sum(r / (m_i + 1)) = 1
    =>  r = 1 / sum(1 / (m_i + 1))

With multipliers (5,5,5,5,10,15,25,45):
    sum(1/(m+1)) = 4/6 + 1/11 + 1/16 + 1/26 + 1/46 ~= 0.880277
    r ~= 1.1360  (113.6% — the house always loses over time)

The DB odds_table is seeded from here; the admin dashboard may tune it later,
but the app always displays the live DB table.
"""

from decimal import Decimal, getcontext

getcontext().prec = 28

# (position, name, multiplier). Names are plain text — no logos or brand assets.
SLOTS: list[tuple[int, str, int]] = [
    (0, "Toyota", 5),
    (1, "Ford", 5),
    (2, "Honda", 5),
    (3, "Nissan", 5),
    (4, "Lamborghini", 10),
    (5, "Pagani", 15),
    (6, "Mercedes-Maybach", 25),
    (7, "Bugatti Chiron", 45),
]


def uniform_rtp() -> Decimal:
    """r = 1 / sum(1/(m_i+1))"""
    total = sum(Decimal(1) / Decimal(m + 1) for _, _, m in SLOTS)
    return Decimal(1) / total


def slot_probabilities() -> list[Decimal]:
    """p_i = r / (m_i + 1); sums to exactly 1 by construction."""
    r = uniform_rtp()
    return [r / Decimal(m + 1) for _, _, m in SLOTS]
