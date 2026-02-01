# bot/handlers/user/whoami.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main import main_menu_kb
from bot.utils.ensure_user import ensure_user

router = Router()


def _get_user_telegram_id(db_user: object, msg: Message) -> int:
    # Try common model field names safely
    for attr in ("tg_id", "telegram_id", "user_id"):
        if hasattr(db_user, attr):
            v = getattr(db_user, attr)
            if isinstance(v, int):
                return v
    # Fallback to Telegram update user id
    return int(msg.from_user.id)


@router.message(Command("whoami"))
async def whoami(message: Message, session: AsyncSession) -> None:
    u = await ensure_user(session, message)

    telegram_id = _get_user_telegram_id(u, message)
    username = f"@{message.from_user.username}" if message.from_user.username else "(none)"

    # Role: if you store role differently, keep your old role calculation.
    role = getattr(u, "role", "user")

    text = (
        "👤 <b>Your identity</b>\n"
        f"• Telegram ID: <code>{telegram_id}</code>\n"
        f"• Username: {username}\n"
        f"• Role: {role}\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
