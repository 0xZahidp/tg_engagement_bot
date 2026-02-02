# bot/services/poll_scheduler.py
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from aiogram import Bot

from bot.database import Database
from bot.services.polls import PollService

log = logging.getLogger("bot.poll_scheduler")


async def poll_scheduler_loop(bot: Bot, db: Database, *, interval_seconds: int = 15) -> None:
    while True:
        now = datetime.utcnow()

        try:
            async with db.session() as session:
                # 1) Post due polls
                due = await PollService.list_due_to_post(session, now, limit=10)
                for p in due:
                    try:
                        options = json.loads(p.options_json)

                        msg = await bot.send_poll(
                            chat_id=p.chat_id,
                            question=p.question,
                            options=options,
                            is_anonymous=False,
                            allows_multiple_answers=False,
                        )

                        try:
                            await bot.pin_chat_message(
                                chat_id=p.chat_id,
                                message_id=msg.message_id,
                                disable_notification=True,
                            )
                        except Exception:
                            pass

                        await PollService.mark_posted(
                            session,
                            poll_id=p.id,
                            telegram_poll_id=msg.poll.id,
                            message_id=msg.message_id,
                            posted_at_utc=now,
                        )
                        log.info("Posted poll id=%s chat=%s msg=%s", p.id, p.chat_id, msg.message_id)
                    except Exception:
                        log.exception("Failed to post poll id=%s", p.id)

                # 2) Close due polls
                due_close = await PollService.list_due_to_close(session, now, limit=10)
                for p in due_close:
                    try:
                        if p.message_id is not None:
                            try:
                                await bot.stop_poll(chat_id=p.chat_id, message_id=p.message_id)
                            except Exception:
                                pass

                        await PollService.mark_closed(session, poll_id=p.id)
                        awarded = await PollService.award_points_after_close(session, poll_id=p.id, now_utc=now)

                        log.info("Closed poll id=%s awarded=%s", p.id, awarded)
                    except Exception:
                        log.exception("Failed to close poll id=%s", p.id)

        except Exception:
            log.exception("Scheduler tick failed")

        await asyncio.sleep(interval_seconds)
