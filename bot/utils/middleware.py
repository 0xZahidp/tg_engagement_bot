# bot/utils/middleware.py
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import Database

log = logging.getLogger("bot.middleware.db")


class DbSessionMiddleware(BaseMiddleware):
    """
    Per-update DB session injected as data["session"].
    Works for ALL update types (Message, CallbackQuery, PollAnswer, etc.).
    Auto-commit on success, rollback on error.
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.db.session() as session:  # type: AsyncSession
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                try:
                    await session.rollback()
                except Exception:
                    pass
                log.exception("DB middleware: unhandled exception")
                raise