from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from bot.config.settings import Settings
from bot.utils.quiz_parser import parse_quiz_set
from bot.database.repo.quiz_repo import get_quiz_for_day, replace_quiz_for_day
from bot.services.auth import AuthService
from bot.database.models import Quiz, QuizOption

log = logging.getLogger(__name__)
router = Router()


def _utc_today() -> datetime.date:
    return datetime.now(tz=ZoneInfo("UTC")).date()


async def require_admin_or_reply(message: Message, settings: Settings, session: AsyncSession) -> bool:
    """
    Checks if sender is admin (root env or DB admin).
    Replies with deny message and returns False if not allowed.
    Also upserts the user record (via AuthService.resolve_by_telegram).
    """
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed to use admin commands.")
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
        await message.answer("⛔ You are not allowed to use admin commands.")
        return False

    return True


def _format_quiz(quiz: Quiz) -> str:
    lines = [
        "🧠 <b>Today's Quiz</b>",
        f"📅 <b>Day (UTC):</b> {quiz.day_utc.isoformat()}",
        f"❓ <b>Q:</b> {quiz.question}",
        f"⭐ <b>Points (correct):</b> {quiz.points_correct}",
        "",
    ]

    # Relationship is ordered by QuizOption.index already
    for o in quiz.options or []:
        is_correct = (o.index == quiz.correct_option_index)  # 0-based
        marker = "✅" if is_correct else "▫️"
        lines.append(f"{marker} <b>{o.index + 1}.</b> {o.text}")

    return "\n".join(lines)


@router.message(F.text == "🧠 Quiz Admin")
async def quiz_admin_panel(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    today_utc = _utc_today()
    quiz = await get_quiz_for_day(session, today_utc)

    help_text = (
        "🧠 <b>Quiz Admin</b>\n\n"
        "Create/replace today's quiz (UTC day) using:\n"
        '<code>/quiz_set "Question" | "A" | "B" | "C" | correct=2 | points=10</code>\n\n'
        "Other commands:\n"
        "<code>/quiz_show</code> — show today's quiz\n"
        "<code>/quiz_clear</code> — delete today's quiz\n"
    )

    if quiz:
        await message.answer(help_text + "\n\n" + _format_quiz(quiz))
    else:
        await message.answer(help_text + f"\n\nℹ️ No quiz set for today yet (UTC: {today_utc.isoformat()}).")


@router.message(F.text.startswith("/quiz_set"))
async def quiz_set_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    try:
        parsed = parse_quiz_set(message.text or "")
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return

    today_utc = _utc_today()

    # create/replace
    await replace_quiz_for_day(
        session=session,
        day_utc=today_utc,
        question=parsed.question,
        options=parsed.options,
        correct_index_1based=parsed.correct_index,
        points_correct=parsed.points,
        points_wrong=0,
        created_by_user_id=None,
    )
    await session.commit()

    # ✅ re-fetch with options eagerly loaded (prevents MissingGreenlet)
    quiz = await get_quiz_for_day(session, today_utc)
    if not quiz:
        await message.answer("✅ Quiz set, but failed to reload quiz for display.")
        return

    await message.answer("✅ Today's quiz (UTC day) has been set/replaced.\n\n" + _format_quiz(quiz))


@router.message(F.text == "/quiz_show")
async def quiz_show_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    today_utc = _utc_today()
    quiz = await get_quiz_for_day(session, today_utc)
    if not quiz:
        await message.answer(f"ℹ️ No quiz set for today (UTC: {today_utc.isoformat()}).")
        return

    await message.answer(_format_quiz(quiz))


@router.message(F.text == "/quiz_clear")
async def quiz_clear_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    today_utc = _utc_today()
    quiz = await get_quiz_for_day(session, today_utc)
    if not quiz:
        await message.answer(f"ℹ️ No quiz to delete for today (UTC: {today_utc.isoformat()}).")
        return

    await session.execute(delete(QuizOption).where(QuizOption.quiz_id == quiz.id))
    await session.execute(delete(Quiz).where(Quiz.id == quiz.id))
    await session.commit()

    await message.answer("✅ Deleted today's quiz (UTC day).")
