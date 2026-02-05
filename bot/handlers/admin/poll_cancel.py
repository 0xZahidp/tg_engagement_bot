# bot/handlers/admin/poll_cancel.py
from __future__ import annotations

from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.auth import AuthService
from bot.services.polls import PollService

router = Router()


async def require_admin(message: Message, settings: Settings, session: AsyncSession) -> bool:
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed.")
        return False

    auth = AuthService(settings)
    authz = await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )
    if not authz.is_admin:
        await message.answer("⛔ You are not allowed.")
        return False
    return True


@router.message(F.text == "/poll_cancel")
async def cmd_poll_cancel(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin(message, settings, session):
        return

    chat_id = int(settings.group_id)
    poll = await PollService.get_active_posted_poll(session, chat_id=chat_id)
    if not poll or not poll.message_id:
        await message.answer("📭 No active poll to cancel.")
        return

    now = datetime.utcnow()

    # Stop Telegram poll
    try:
        await message.bot.stop_poll(chat_id=poll.chat_id, message_id=poll.message_id)
    except Exception:
        # even if it fails, we still cancel in DB to stop points logic
        pass

    await PollService.mark_canceled(session, poll_id=poll.id, now_utc=now)
    await session.commit()

    await message.answer(
        "✅ Poll canceled.\n"
        f"• Poll ID: {poll.id}\n"
        "• No more votes/points for this poll."
    )