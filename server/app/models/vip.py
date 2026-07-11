"""VIP tables. Tiers are EARNED by daily winnings, never bought (Prime Directive 1).
A higher tier replaces the current one immediately; durations never stack."""

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VipStatus(Base):
    __tablename__ = "vip_status"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint("tier BETWEEN 1 AND 5", name="ck_vip_tier_range"),)


class DailyWinningsCounter(Base):
    """Coins won today (Asia/Dhaka); resets at midnight. Drives VIP awards."""

    __tablename__ = "daily_winnings_counter"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    coins_won: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
