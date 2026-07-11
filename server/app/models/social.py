"""Social-side tables: voice-room Tables, roles/moderation, friends, DMs, safety."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, IdMixin


class Table(Base, IdMixin, CreatedAtMixin):
    """A public voice room."""

    __tablename__ = "tables"

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(48), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(120))
    chair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("chair_count IN (8, 10, 12)", name="ck_tables_chair_count"),
        CheckConstraint("status IN ('open','closed')", name="ck_tables_status"),
    )


class TableRole(Base, IdMixin, CreatedAtMixin):
    """Admin grants. The owner is implicit via tables.owner_id."""

    __tablename__ = "table_roles"

    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("table_id", "user_id", name="uq_table_roles"),)


class TableBlock(Base, IdMixin, CreatedAtMixin):
    """Owner block: user cannot enter this Table at all — overrides VIP Anti-Kick."""

    __tablename__ = "table_blocks"

    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("table_id", "user_id", name="uq_table_blocks"),)


class TableChatBan(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "table_chat_bans"

    table_id: Mapped[int] = mapped_column(
        ForeignKey("tables.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    banned_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    __table_args__ = (UniqueConstraint("table_id", "user_id", name="uq_table_chat_bans"),)


class FriendRequest(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "friend_requests"

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','accepted','declined','cancelled')",
            name="ck_friend_requests_status",
        ),
        CheckConstraint("sender_id != recipient_id", name="ck_friend_requests_not_self"),
        Index("ix_friend_requests_recipient", "recipient_id", "status"),
    )


class Friendship(Base, IdMixin, CreatedAtMixin):
    """Stored once per pair with user_a_id < user_b_id. Friends are NEVER
    auto-deleted when a VIP friend limit drops (grandfather rule)."""

    __tablename__ = "friendships"

    user_a_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_b_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_friendships_pair"),
        CheckConstraint("user_a_id < user_b_id", name="ck_friendships_ordered"),
        Index("ix_friendships_b", "user_b_id"),
    )


class PendingMessage(Base, IdMixin, CreatedAtMixin):
    """Store-and-forward DMs: exists ONLY while the recipient is offline.
    Deleted immediately on delivery; purged after 30 days by a scheduled job.
    Message history lives on users' devices, not this server."""

    __tablename__ = "pending_messages"

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_pending_messages_recipient", "recipient_id"),
        Index("ix_pending_messages_created", "created_at"),  # for the 30-day purge
    )


class UserBlock(Base, IdMixin, CreatedAtMixin):
    """Personal block: blocker no longer hears or sees the blocked user anywhere."""

    __tablename__ = "user_blocks"

    blocker_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks"),
        CheckConstraint("blocker_id != blocked_id", name="ck_user_blocks_not_self"),
    )


class Report(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "reports"

    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reported_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    table_id: Mapped[int | None] = mapped_column(ForeignKey("tables.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status IN ('open','resolved')", name="ck_reports_status"),
        Index("ix_reports_status", "status"),
    )
