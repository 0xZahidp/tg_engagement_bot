# bot/utils/middleware.py
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.session import Database
from bot.database.repo.users import upsert_user_from_event


class DbSessionMiddleware(BaseMiddleware):
    """
    Creates a DB session per update and injects it into handler data as `session`.

    Also upserts the current Telegram user (if present) and injects it as `db_user`.
    Auto-commits on success and rolls back on error.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.db.SessionLocal() as session:  # type: ignore[attr-defined]
            data["session"] = session

            # Upsert DB user for message/callback/etc updates (when user exists)
            db_user = await upsert_user_from_event(session, event)
            if db_user is not None:
                data["db_user"] = db_user

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
 