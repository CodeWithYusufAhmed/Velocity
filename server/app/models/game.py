"""Game-side tables: users, auth, rounds, bets, ledger, odds, settings, stats."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class User(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(32), nullable=False)
    # Virtual coins only — never purchasable or transferable (Prime Directive 1).
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Small circular profile picture (pulled forward from later-feature by Yusuf, M10).
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary)
    avatar_mime: Mapped[str | None] = mapped_column(String(32))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # In-app moderator (Velocity owner): gifts VIP/coins, timed bans, sees reports.
    is_moderator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("balance >= 0", name="ck_users_balance_nonneg"),)


class Credential(Base, IdMixin, CreatedAtMixin):
    """Argon2id password hash, separate from users so Google-only accounts have no row."""

    __tablename__ = "credentials"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base, IdMixin, CreatedAtMixin):
    """Rotating refresh tokens; a used or revoked token can never be replayed."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[int | None] = mapped_column(ForeignKey("refresh_tokens.id"))


class OddsSlot(Base, IdMixin):
    """The live wheel configuration. Names are plain text so a slot can be
    renamed instantly (trademark caution) without an app update. Probabilities
    are engineered so every slot has identical player-favored RTP:
    with payout (m+1)*stake, uniform RTP r needs sum(r/(m_i+1)) = 1, giving
    r ~= 1.1360 and p_i = r/(m_i+1)."""

    __tablename__ = "odds_table"

    position: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)  # 0..7 on the wheel
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    multiplier: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[float] = mapped_column(Numeric(12, 10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("multiplier > 0", name="ck_odds_multiplier_pos"),
        CheckConstraint("probability > 0 AND probability < 1", name="ck_odds_prob_range"),
    )


class Round(Base):
    """One global round. id is the sequential round number shown in the app.
    commit is published when betting opens; server_seed revealed at results —
    stored forever so any player can re-verify (provably fair)."""

    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commit: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hex
    server_seed: Mapped[str | None] = mapped_column(String(64))  # hex, NULL until reveal
    winning_position: Mapped[int | None] = mapped_column(Integer)
    betting_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Top 3 winners of the round, stored forever (spec A6): [{user_id, display_name, won}]
    top3: Mapped[list | None] = mapped_column(JSON)


class Bet(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "bets"

    round_id: Mapped[int] = mapped_column(
        ForeignKey("rounds.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    slot_position: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payout: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bets_amount_pos"),
        Index("ix_bets_round_user", "round_id", "user_id"),
        Index("ix_bets_user_created", "user_id", "created_at"),
    )


class Transaction(Base, IdMixin, CreatedAtMixin):
    """Append-only ledger: every balance change has exactly one row here."""

    __tablename__ = "transactions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # signed delta
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    round_id: Mapped[int | None] = mapped_column(ForeignKey("rounds.id"))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "type IN ('signup','bet','win','daily_bonus','rescue','admin_adjust')",
            name="ck_transactions_type",
        ),
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Self-set daily round limit (anti-addiction). NULL = off.
    daily_round_limit: Mapped[int | None] = mapped_column(Integer)
    # A raised limit only applies from the NEXT day; lowering applies immediately.
    pending_round_limit: Mapped[int | None] = mapped_column(Integer)
    pending_limit_effective_date: Mapped[date | None] = mapped_column(Date)
    studio_noise_removal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DailyStats(Base):
    """Per-user per-day aggregates (Asia/Dhaka days): drives leaderboards,
    the round limit, rescue caps, and the daily bonus claim."""

    __tablename__ = "daily_stats"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    rounds_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_bet: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_won: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rescues_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus_claimed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    biggest_win: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    __table_args__ = (Index("ix_daily_stats_day", "day"),)


class AdminAudit(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "admin_audit"

    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    detail: Mapped[str | None] = mapped_column(Text)
