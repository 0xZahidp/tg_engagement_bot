# bot/services/quiz_service.py
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.quiz import Quiz, QuizAttempt
from bot.database.models.daily_action import DailyAction, DailyActionType

# points service: try both common names (so it won’t break if yours differs)
try:
    from bot.services.points import add_points  # type: ignore
except Exception:
    add_points = None  # noqa: E501


def utc_today() -> datetime.date:
    return datetime.now(timezone.utc).date()


async def get_today_quiz(session: AsyncSession) -> dict | None:
    today = utc_today()

    quiz = await session.scalar(
        select(Quiz)
        .where(Quiz.day_utc == today)
        .options(selectinload(Quiz.options))
    )
    if quiz is None:
        return None

    options = [opt.text for opt in quiz.options]  # ordered by relationship order_by
    return {
        "id": quiz.id,
        "question": quiz.question,
        "options": options,
        "correct_index": quiz.correct_option_index,
        "points_correct": quiz.points_correct,
        "points_wrong": quiz.points_wrong,
        "day_utc": quiz.day_utc,
    }


async def has_attempted_today(session: AsyncSession, user_id: int, quiz_id: int) -> bool:
    today = utc_today()
    exists = await session.scalar(
        select(QuizAttempt.id).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.quiz_id == quiz_id,
            QuizAttempt.day_utc == today,
        )
    )
    return exists is not None


async def submit_attempt(session: AsyncSession, user_id: int, quiz_id: int, chosen_index: int) -> dict:
    quiz = await get_today_quiz(session)
    if quiz is None or quiz["id"] != quiz_id:
        return {"ok": False, "message": "⚠️ This quiz is not valid anymore.", "points_delta": 0}

    today = quiz["day_utc"]

    # hard check first
    if await has_attempted_today(session, user_id=user_id, quiz_id=quiz_id):
        return {"ok": False, "message": "✅ You already answered today’s quiz.", "points_delta": 0}

    is_correct = int(chosen_index) == int(quiz["correct_index"])
    points = int(quiz["points_correct"] if is_correct else quiz["points_wrong"])

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=user_id,
        day_utc=today,
        chosen_index=int(chosen_index),
        is_correct=1 if is_correct else 0,
        points_awarded=points,
    )
    action = DailyAction(
        user_id=user_id,
        day_utc=today,
        action_type=DailyActionType.QUIZ.value,
    )

    session.add(attempt)
    session.add(action)

    try:
        # points (if you have add_points in your project)
        if points and add_points is not None:
            await add_points(session, user_id=user_id, delta=points, reason="quiz")

        # commit happens in middleware, but we must catch unique-constraint races
        return {
            "ok": True,
            "message": (f"✅ Correct! +{points} points." if is_correct else "❌ Wrong answer. Try again tomorrow (UTC)."),
            "points_delta": points,
        }

    except IntegrityError:
        # user spam clicked; unique constraint blocked duplicate rows
        await session.rollback()
        return {"ok": False, "message": "✅ You already answered today’s quiz.", "points_delta": 0}
