"""Reports and personal blocks (spec B1 Safety)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, User, UserBlock


class SafetyError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def report_user(session: AsyncSession, reporter_id: int, reported_id: int,
                      reason: str, note: str | None, table_id: int | None) -> Report:
    if reporter_id == reported_id:
        raise SafetyError("You cannot report yourself")
    if await session.get(User, reported_id) is None:
        raise SafetyError("User not found", 404)
    r = Report(reporter_id=reporter_id, reported_id=reported_id,
               reason=reason, note=note, table_id=table_id)
    session.add(r)
    await session.commit()
    return r


async def block_user(session: AsyncSession, blocker_id: int, blocked_id: int) -> None:
    if blocker_id == blocked_id:
        raise SafetyError("You cannot block yourself")
    if await session.get(User, blocked_id) is None:
        raise SafetyError("User not found", 404)
    exists = await session.scalar(select(UserBlock).where(
        UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id))
    if not exists:
        session.add(UserBlock(blocker_id=blocker_id, blocked_id=blocked_id))
        await session.commit()


async def unblock_user(session: AsyncSession, blocker_id: int, blocked_id: int) -> None:
    row = await session.scalar(select(UserBlock).where(
        UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id))
    if row:
        await session.delete(row)
        await session.commit()


async def blocked_ids(session: AsyncSession, user_id: int) -> set[int]:
    """Users this user has personally blocked (never see/hear them anywhere)."""
    rows = await session.scalars(
        select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id))
    return set(rows.all())
