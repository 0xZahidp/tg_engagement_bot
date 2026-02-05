# bot/handlers/user/poll.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.polls import PollService
from bot.keyboards.main import BTN_POLL

router = Router()


def chat_message_link(chat_id: int, message_id: int, public_username: str | None = None) -> str:
    if public_username:
        return f"https://t.me/{public_username}/{message_id}"

    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"

    # fallback (may not work for non-supergroups)
    return f"https://t.me/c/{abs(chat_id)}/{message_id}"


async def _send_active_poll(message: Message, settings: Settings, session: AsyncSession) -> None:
    chat_id = int(settings.group_id)
    poll = await PollService.get_active_posted_poll(session, chat_id=chat_id)

    if not poll or not poll.message_id:
        await message.answer("📭 No active poll right now.")
        return

    url = chat_message_link(chat_id, poll.message_id, public_username=getattr(settings, "group_username", None))
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗳️ Vote Now", url=url)]])

    await message.answer(
        "📊 <b>Today’s Poll</b>\n\n"
        "Tap <b>Vote Now</b> to open the poll in the group and vote.\n"
        "✅ Vote can’t be changed.\n"
        "✅ Points will be added instantly after voting.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(Command("poll"))
async def cmd_poll_user(message: Message, settings: Settings, session: AsyncSession) -> None:
    await _send_active_poll(message, settings, session)


@router.message(lambda m: (m.text or "").strip() == BTN_POLL)
async def btn_poll_user(message: Message, settings: Settings, session: AsyncSession) -> None:
    await _send_active_poll(message, settings, session)