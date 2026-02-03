from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.models import PointSource, User
from bot.database.repo.points_repo import award_points_once
from bot.database.repo.quiz_attempt_repo import (
    create_attempt_once,
    get_attempt,
    get_quiz_by_id,
)
from bot.database.repo.quiz_repo import get_quiz_for_day
from bot.services.auth import AuthService
from bot.services.task_progress import TaskProgressService
from bot.utils.reply import reply_safe

log = logging.getLogger(__name__)
router = Router()


def _utc_today():
    return datetime.now(tz=ZoneInfo("UTC")).date()


def _quiz_keyboard(quiz_id: int, options: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for idx, text in enumerate(options):
        rows.append(
            [InlineKeyboardButton(text=text, callback_data=f"quiz:{quiz_id}:{idx}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _get_or_create_user(
    session: AsyncSession, settings: Settings, tg_user
) -> User | None:
    if not tg_user:
        return None

    auth = AuthService(settings)
    await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )

    res = await session.execute(select(User).where(User.telegram_id == tg_user.id))
    return res.scalar_one_or_none()


@router.message(F.text == "🧠 Quiz")
@router.message(F.text == "/quiz")
async def quiz_entry(message: Message, settings: Settings, session: AsyncSession) -> None:
    user = await _get_or_create_user(session, settings, message.from_user)
    if not user:
        await reply_safe(message, "⚠️ Please try again.")
        return

    today_utc = _utc_today()
    quiz = await get_quiz_for_day(session, today_utc)
    if not quiz:
        await reply_safe(
            message,
            f"ℹ️ No quiz set for today (UTC: {today_utc.isoformat()}).",
        )
        return

    existing = await get_attempt(session, quiz.id, user.id)
    if existing:
        status = "✅ Correct" if int(existing.is_correct or 0) == 1 else "❌ Wrong"
        await reply_safe(
            message,
            (
                "🧠 <b>Today's Quiz (UTC)</b>\n\n"
                f"❓ {quiz.question}\n\n"
                f"{status}! <b>Points:</b> {int(existing.points_awarded or 0)}"
            ),
            parse_mode="HTML",
        )
        return

    option_texts = [o.text for o in (quiz.options or [])]
    kb = _quiz_keyboard(quiz.id, option_texts)

    # ✅ Inline keyboard is allowed in group
    await message.answer(
        (
            "🧠 <b>Today's Quiz (UTC)</b>\n\n"
            f"❓ {quiz.question}\n\n"
            "Choose one option:"
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("quiz:"))
async def quiz_answer(
    cb: CallbackQuery, settings: Settings, session: AsyncSession
) -> None:
    try:
        await cb.answer()
    except Exception:
        pass

    if not cb.message:
        return

    user = await _get_or_create_user(session, settings, cb.from_user)
    if not user:
        await reply_safe(cb.message, "⚠️ Please try again.")
        return

    try:
        _, quiz_id_s, chosen_s = (cb.data or "").split(":")
        quiz_id = int(quiz_id_s)
        chosen_index = int(chosen_s)
    except Exception:
        await reply_safe(cb.message, "❌ Invalid answer payload.")
        return

    today_utc = _utc_today()

    quiz = await get_quiz_by_id(session, quiz_id)
    if not quiz:
        await reply_safe(cb.message, "ℹ️ Quiz not found.")
        return

    if quiz.day_utc != today_utc:
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await reply_safe(cb.message, "ℹ️ This quiz is no longer active.")
        return

    try:
        result = await create_attempt_once(
            session,
            quiz=quiz,
            user_id=user.id,
            day_utc=today_utc,
            chosen_index=chosen_index,
        )
    except ValueError:
        await reply_safe(cb.message, "❌ Invalid choice.")
        return

    if result.already_attempted:
        await session.rollback()
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await reply_safe(cb.message, "ℹ️ You already attempted today’s quiz.")
        return

    # ✅ KEY FIX: mark quiz done on SUCCESSFUL ATTEMPT (right or wrong, points or no points)
    await TaskProgressService.mark_done(
        session,
        user_id=user.id,
        day_utc=today_utc,
        action_type="quiz",
    )

    awarded_points = result.points_awarded
    if awarded_points != 0:
        award = await award_points_once(
            session,
            user_id=user.id,
            day_utc=today_utc,
            source=PointSource.QUIZ,
            points=awarded_points,
            ref_type="quiz",
            ref_id=quiz.id,
        )
        if not award.awarded:
            await session.commit()
            try:
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            status = "✅ Correct" if result.is_correct else "❌ Wrong"
            await reply_safe(
                cb.message,
                f"{status}! <b>Points:</b> 0 (already credited)",
                parse_mode="HTML",
            )
            return

    await session.commit()

    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    status = "✅ Correct" if result.is_correct else "❌ Wrong"
    await reply_safe(
        cb.message,
        f"{status}! <b>Points:</b> {awarded_points}",
        parse_mode="HTML",
    )
