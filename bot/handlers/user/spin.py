# bot/handlers/user/spin.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.spin import SpinService
from bot.utils.dates import utc_today
from bot.utils.ensure_user import ensure_user
from bot.utils.reply import reply_safe

router = Router()

SPIN_BUTTON_TEXT = "🎰 Spin"


@router.message(Command("spin"))
@router.message(lambda m: (m.text or "").strip() == SPIN_BUTTON_TEXT)
async def spin_cmd(message: Message, session: AsyncSession) -> None:
    user = await ensure_user(session, message)
    day_utc = utc_today()

    # Until poll is implemented
    require_poll = False

    res = await SpinService.spin(
        session,
        user_id=user.id,
        day_utc=day_utc,
        require_poll=require_poll,
    )

    await reply_safe(
        message,
        res.message,
        parse_mode="HTML",
    )
