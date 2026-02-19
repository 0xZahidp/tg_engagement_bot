from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


def schedule_delete(bot, chat_id: int, message_id: int, delay_seconds: int = 60) -> None:
    async def _job() -> None:
        log.info("Auto-delete scheduled chat_id=%s msg_id=%s in %ss", chat_id, message_id, delay_seconds)
        await asyncio.sleep(delay_seconds)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            log.info("Auto-deleted chat_id=%s msg_id=%s", chat_id, message_id)
        except Exception:
            log.exception("Auto-delete failed chat_id=%s msg_id=%s", chat_id, message_id)

    asyncio.create_task(_job())
