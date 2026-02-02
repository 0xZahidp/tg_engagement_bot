from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.ensure_user import ensure_user
from bot.utils.reply import reply_safe

router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message, session: AsyncSession) -> None:
    await ensure_user(session, message)

    await reply_safe(
        message,
        "✅ Engagement Bot is running.\n"
        "Use the menu buttons below (commands also work).",
    )
