# bot/utils/autodelete_bot.py
from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.methods import TelegramMethod
from aiogram.types import Message

from bot.config.settings import Settings
from bot.utils.autodelete import schedule_delete


class AutoDeleteBot(Bot):
    def __init__(self, *args, settings: Settings, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings = settings

    @staticmethod
    def _is_approved_screenshot_caption(caption: str) -> bool:
        """
        Robust check:
        Telegram may normalize/strip HTML (<b>) or emojis.
        We just ensure the phrase exists.
        """
        c = (caption or "").lower()
        return "approved screenshot" in c

    def _should_autodelete_message(self, msg: Message) -> bool:
        gid = self._settings.group_id
        if not gid:
            return False

        # Only MAIN GROUP
        if int(msg.chat.id) != int(gid):
            return False

        # Keep polls (poll must remain)
        if getattr(msg, "poll", None) is not None:
            return False

        # Keep approved screenshot post
        caption = getattr(msg, "caption", None) or ""
        if self._is_approved_screenshot_caption(caption):
            return False

        return True

    def _schedule_if_needed(self, result: Any) -> None:
        # Some API calls return Message, some return list[Message]
        if isinstance(result, Message):
            if self._should_autodelete_message(result):
                schedule_delete(self, result.chat.id, result.message_id, 60)

        elif isinstance(result, list) and result and all(isinstance(x, Message) for x in result):
            for m in result:
                if self._should_autodelete_message(m):
                    schedule_delete(self, m.chat.id, m.message_id, 60)

    async def __call__(
        self,
        method: TelegramMethod[Any],
        request_timeout: int | None = None,
    ) -> Any:
        result = await super().__call__(method, request_timeout=request_timeout)
        self._schedule_if_needed(result)
        return result
