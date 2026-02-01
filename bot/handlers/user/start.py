from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main import main_menu_kb
from bot.utils.ensure_user import ensure_user

router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message, session: AsyncSession) -> None:
    await ensure_user(session, message)
    await message.answer(
        "✅ Engagement Bot is running.\n"
        "Use the menu buttons below (commands also work).",
        reply_markup=main_menu_kb(),
    )
