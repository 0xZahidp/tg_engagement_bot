# bot/handlers/user/checkin.py
from __future__ import annotations

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main import main_menu_kb
from bot.services.checkin import CheckinService
from bot.utils.dates import utc_today
from bot.utils.ensure_user import ensure_user

router = Router()

CHECKIN_BUTTON_TEXT = "✅ Check-in"


@router.message(Command("checkin"))
@router.message(lambda m: (m.text or "").strip() == CHECKIN_BUTTON_TEXT)
async def checkin(message: Message, session: AsyncSession) -> None:
    user = await ensure_user(session, message)

    day_utc = utc_today()
    res = await CheckinService.checkin(session, user_id=user.id, day_utc=day_utc)

    if res.already:
        text = (
            "✅ <b>Already checked in today</b>\n"
            f"• Week points: <b>{res.week_points}</b>\n"
            f"• Week streak: <b>{res.week_streak}</b>\n\n"
            "Come back tomorrow (UTC)."
        )
    else:
        text = (
            "🔥 <b>Check-in successful!</b>\n"
            f"• +<b>{res.points_awarded}</b> points\n"
            f"• Week points: <b>{res.week_points}</b>\n"
            f"• Week streak: <b>{res.week_streak}</b>"
        )

    await message.answer(html.unescape(text), parse_mode="HTML", reply_markup=main_menu_kb())
