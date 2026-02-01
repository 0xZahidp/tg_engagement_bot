# bot/handlers/user/status.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main import main_menu_kb
from bot.services.task_progress import TaskProgressService
from bot.utils.dates import utc_today
from bot.utils.ensure_user import ensure_user

router = Router()

STATUS_BUTTON_TEXT = "📌 Status"


@router.message(Command("status"))
@router.message(lambda m: (m.text or "").strip() == STATUS_BUTTON_TEXT)
async def status_cmd(message: Message, session: AsyncSession) -> None:
    user = await ensure_user(session, message)
    day_utc = utc_today()

    done = await TaskProgressService.done_set(session, user_id=user.id, day_utc=day_utc)

    text = (
        "📌 <b>Today’s progress (UTC)</b>\n"
        f"• checkin: {'✅' if 'checkin' in done else '❌'}\n"
        f"• quiz: {'✅' if 'quiz' in done else '❌'}\n"
        f"• poll: {'✅' if 'poll_vote' in done else '❌'}\n"
        f"• screenshot: {'✅' if 'screenshot' in done else '❌'}\n"
        f"• spin: {'✅' if 'spin' in done else '❌'}\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
