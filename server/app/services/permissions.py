"""The Table moderation permission matrix (spec B1), as pure functions so it
can be tested exhaustively.

Roles: "owner" > "admin" > "user".
Outcomes: "ok" — perform it; "anti_kick" — kick fails, tell the admin why;
"forbidden" — reject.

Rules:
- Owner may kick/mute/chat-ban anyone, and is the only one who may block or
  grant/revoke admin. Owner's kick works even on VIP3+ (owner also holds the
  stronger block power); owner's BLOCK overrides Anti-Kick by definition.
- Admins act on non-admins only; their kick fails against VIP3+ (Anti-Kick),
  surfaced as "anti_kick" so the UI can show "This user has Anti-Kick".
- Nobody targets the owner. Users moderate nobody.
"""

from app.services.vip import has_anti_kick

OWNER, ADMIN, USER = "owner", "admin", "user"


def _admin_may_target(target_role: str) -> bool:
    return target_role == USER


def can_kick(actor_role: str, target_role: str, target_vip_tier: int) -> str:
    if target_role == OWNER:
        return "forbidden"
    if actor_role == OWNER:
        return "ok"
    if actor_role == ADMIN and _admin_may_target(target_role):
        return "anti_kick" if has_anti_kick(target_vip_tier) else "ok"
    return "forbidden"


def can_mute(actor_role: str, target_role: str) -> str:
    if target_role == OWNER:
        return "forbidden"
    if actor_role == OWNER:
        return "ok"
    if actor_role == ADMIN and _admin_may_target(target_role):
        return "ok"  # Anti-Kick protects against kicks only, not mutes
    return "forbidden"


def can_chat_ban(actor_role: str, target_role: str) -> str:
    if target_role == OWNER:
        return "forbidden"
    if actor_role == OWNER:
        return "ok"
    if actor_role == ADMIN and _admin_may_target(target_role):
        return "ok"
    return "forbidden"


def can_block(actor_role: str, target_role: str) -> str:
    """Table-level block: owner only; blocks anyone else (overrides Anti-Kick)."""
    if actor_role == OWNER and target_role != OWNER:
        return "ok"
    return "forbidden"


def can_grant_admin(actor_role: str) -> str:
    return "ok" if actor_role == OWNER else "forbidden"


def can_close_table(actor_role: str) -> str:
    return "ok" if actor_role == OWNER else "forbidden"
