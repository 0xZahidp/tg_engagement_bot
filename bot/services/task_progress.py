# bot/services/task_progress.py
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyAction, DailyActionType


def _normalize_action_type(action_type: DailyActionType | str) -> str:
    if isinstance(action_type, DailyActionType):
        return action_type.value
    return str(action_type).strip()


class TaskProgressService:
    @staticmethod
    async def mark_done(
        session: AsyncSession,
        *,
        user_id: int,
        day_utc: date,
        action_type: DailyActionType | str,
    ) -> None:
        at = _normalize_action_type(action_type)

        # ✅ Use a SAVEPOINT so duplicates don't rollback the whole session
        try:
            async with session.begin_nested():
                session.add(DailyAction(user_id=user_id, day_utc=day_utc, action_type=at))
                await session.flush()
        except IntegrityError:
            # duplicate => already done, ignore
            return

    @staticmethod
    async def done_set(session: AsyncSession, *, user_id: int, day_utc: date) -> set[str]:
        res = await session.execute(
            select(DailyAction.action_type).where(
                DailyAction.user_id == user_id,
                DailyAction.day_utc == day_utc,
            )
        )
        return {row[0] for row in res.all()}
