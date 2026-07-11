"""seed odds_table

Revision ID: e6d60a978b13
Revises: 08a2da6911d5
Create Date: 2026-07-11 13:27:58.368652

Seeds the wheel from app.game.odds — the canonical uniform-RTP math
(r = 1/sum(1/(m_i+1)) ~= 113.6%, p_i = r/(m_i+1)).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.game.odds import SLOTS, slot_probabilities

revision: str = 'e6d60a978b13'
down_revision: Union[str, None] = '08a2da6911d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    odds = sa.table(
        "odds_table",
        sa.column("position", sa.Integer),
        sa.column("name", sa.String),
        sa.column("multiplier", sa.Integer),
        sa.column("probability", sa.Numeric),
        sa.column("is_active", sa.Boolean),
    )
    probs = slot_probabilities()
    op.bulk_insert(
        odds,
        [
            {
                "position": pos,
                "name": name,
                "multiplier": mult,
                "probability": round(probs[pos], 10),
                "is_active": True,
            }
            for pos, name, mult in SLOTS
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM odds_table")
