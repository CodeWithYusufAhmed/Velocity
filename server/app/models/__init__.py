"""ORM models. Importing this package registers every table on Base.metadata,
which is what Alembic autogenerate inspects."""

from app.models.base import Base
from app.models.game import (
    AdminAudit,
    Bet,
    Credential,
    DailyStats,
    OddsSlot,
    RefreshToken,
    Round,
    Transaction,
    User,
    UserSettings,
)
from app.models.social import (
    FriendRequest,
    Friendship,
    PendingMessage,
    Report,
    Table,
    TableBlock,
    TableChatBan,
    TableRole,
    UserBlock,
)
from app.models.admin import RuntimeSetting
from app.models.vip import DailyWinningsCounter, VipStatus

__all__ = [
    "Base",
    "User", "Credential", "RefreshToken", "Round", "Bet", "Transaction",
    "OddsSlot", "UserSettings", "DailyStats", "AdminAudit",
    "Table", "TableRole", "TableBlock", "TableChatBan",
    "Friendship", "FriendRequest", "PendingMessage", "UserBlock", "Report",
    "VipStatus", "DailyWinningsCounter", "RuntimeSetting",
]
