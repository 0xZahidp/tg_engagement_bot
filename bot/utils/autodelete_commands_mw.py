# bot/utils/autodelete_commands_mw.py
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram.types import Message

from bot.config.settings import Settings
from bot.utils.autodelete import schedule_delete


class AutoDeleteCommandsMiddleware:
    def __init__(self, settings: Settings, delay_seconds: int = 60):
        self.settings = settings
        self.delay_seconds = delay_seconds

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        finally:
            gid = self.settings.group_id
            if not gid:
                return
            if int(event.chat.id) != int(gid):
                return

            text = (event.text or "").strip()
            if text.startswith("/"):
                # Delete user command message after 60s
                schedule_delete(event.bot, event.chat.id, event.message_id, self.delay_seconds)
