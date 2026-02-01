# bot/handlers/user/quiz.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.quiz_service import QuizService

router = Router(name="user.quiz")


def build_quiz_kb(quiz_id: int, options: list) -> object:
    kb = InlineKeyboardBuilder()
    for opt in options:
        # callback uses option INDEX (your correct option is stored as index)
        kb.button(text=opt.text, callback_data=f"qz:ans:{quiz_id}:{opt.index}")
    kb.adjust(1)
    return kb.as_markup()


def render_quiz_text(quiz) -> str:
    # quiz.question already exists in your model
    # options are sent as buttons (cleaner)
    return (
        f"🧠 <b>Daily Quiz</b>\n"
        f"📅 <b>{quiz.day_utc.isoformat()} (UTC)</b>\n\n"
        f"{quiz.question}\n\n"
        f"Choose an option:"
    )


def render_result_text(quiz, chosen_index: int, is_correct: bool, points: int) -> str:
    correct_opt = next((o for o in quiz.options if o.index == quiz.correct_option_index), None)
    chosen_opt = next((o for o in quiz.options if o.index == chosen_index), None)

    correct_text = correct_opt.text if correct_opt else f"Index {quiz.correct_option_index}"
    chosen_text = chosen_opt.text if chosen_opt else f"Index {chosen_index}"

    icon = "✅" if is_correct else "❌"
    return (
        f"🏁 <b>Daily Quiz Result</b>\n"
        f"📅 <b>{quiz.day_utc.isoformat()} (UTC)</b>\n\n"
        f"{quiz.question}\n\n"
        f"{icon} <b>{'Correct' if is_correct else 'Wrong'}</b>\n"
        f"🟦 Your answer: <b>{chosen_text}</b>\n"
        f"🟩 Correct answer: <b>{correct_text}</b>\n\n"
        f"⭐ Points: <b>{points}</b>\n\n"
        f"Come back tomorrow for the next quiz."
    )


@router.message(Command("quiz"))
async def cmd_quiz(message: Message, session: AsyncSession):
    svc = QuizService(session)
    quiz = await svc.get_today_quiz()

    if not quiz:
        return await message.answer("No quiz has been published for today (UTC) yet.")

    # If already attempted, show result summary (no re-try)
    attempt = await svc.get_attempt(quiz.id, message.from_user.id)
    if attempt:
        is_correct = bool(attempt.is_correct)
        text = render_result_text(quiz, attempt.chosen_index, is_correct, attempt.points_awarded)
        return await message.answer(text)

    await message.answer(
        render_quiz_text(quiz),
        reply_markup=build_quiz_kb(quiz.id, quiz.options),
    )


@router.callback_query(F.data.startswith("qz:ans:"))
async def cb_quiz_answer(call: CallbackQuery, session: AsyncSession):
    try:
        _, _, quiz_id_str, chosen_index_str = call.data.split(":")
        quiz_id = int(quiz_id_str)
        chosen_index = int(chosen_index_str)
    except Exception:
        return await call.answer("Invalid data.", show_alert=True)

    svc = QuizService(session)

    # Load quiz + options
    quiz = await svc.get_quiz_for_day(day=call.message.date.date())  # fallback attempt
    # Better: fetch by id (safe)
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from bot.database.models.quiz import Quiz as QuizModel

    res = await session.execute(
        select(QuizModel)
        .where(QuizModel.id == quiz_id)
        .options(selectinload(QuizModel.options))
    )
    quiz = res.scalar_one_or_none()

    if not quiz:
        return await call.answer("Quiz not found.", show_alert=True)

    attempt = await svc.submit_attempt(quiz, call.from_user.id, chosen_index)
    if attempt is None:
        await call.answer("You already answered this quiz.", show_alert=False)
        # Optional: also remove buttons to prevent more clicks
        return

    is_correct = bool(attempt.is_correct)
    text = render_result_text(quiz, chosen_index, is_correct, attempt.points_awarded)

    # Edit message to show result and remove buttons
    await call.message.edit_text(text, reply_markup=None)
    await call.answer("✅ Saved!" if is_correct else "Saved!")
