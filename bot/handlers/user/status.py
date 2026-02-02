# bot/handlers/user/status.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyActionType
from bot.services.task_progress import TaskProgressService
from bot.utils.dates import utc_today
from bot.utils.ensure_user import ensure_user
from bot.utils.reply import reply_safe

router = Router()

STATUS_BUTTON_TEXT = "📌 Status"


@router.message(Command("status"))
@router.message(lambda m: (m.text or "").strip() == STATUS_BUTTON_TEXT)
async def status_cmd(message: Message, session: AsyncSession) -> None:
    user = await ensure_user(session, message)
    day_utc = utc_today()

    done = await TaskProgressService.done_set(
        session, user_id=user.id, day_utc=day_utc
    )

    def ok(t: DailyActionType) -> str:
        return "✅" if t.value in done else "❌"

    text = (
        "📌 <b>Today’s progress (UTC)</b>\n"
        f"• checkin: {ok(DailyActionType.CHECKIN)}\n"
        f"• quiz: {ok(DailyActionType.QUIZ)}\n"
        f"• poll: {ok(DailyActionType.POLL_VOTE)}\n"
        f"• screenshot: {ok(DailyActionType.SCREENSHOT)}\n"
        f"• spin: {ok(DailyActionType.SPIN)}\n"
    )

    await reply_safe(
        message,
        text,
        parse_mode="HTML",
    )
