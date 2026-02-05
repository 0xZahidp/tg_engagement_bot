# bot/handlers/admin/poll_status.py
from __future__ import annotations

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


@router.message(F.text == "/poll_status")
async def cmd_poll_status(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin(message, settings, session):
        return

    chat_id = int(settings.group_id)
    poll = await PollService.get_active_posted_poll(session, chat_id=chat_id)
    if not poll:
        await message.answer("📭 No active poll right now.")
        return

    votes = await PollService.count_votes(session, poll_id=poll.id)

    closes_txt = str(poll.closes_at_utc) if poll.closes_at_utc else "Unknown"
    await message.answer(
        "📊 Poll Status\n"
        f"• Poll ID: {poll.id}\n"
        f"• Votes: {votes}\n"
        f"• Closes (UTC): {closes_txt}\n"
        f"• Question: {poll.question}"
    )