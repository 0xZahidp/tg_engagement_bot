from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Quiz, QuizAttempt


@dataclass(frozen=True, slots=True)
class AttemptResult:
    already_attempted: bool
    is_correct: bool
    points_awarded: int
    chosen_index: int


async def get_quiz_by_id(session: AsyncSession, quiz_id: int) -> Quiz | None:
    q = (
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.options))
    )
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def get_attempt(session: AsyncSession, quiz_id: int, user_id: int) -> QuizAttempt | None:
    q = select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == user_id)
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def create_attempt_once(
    session: AsyncSession,
    *,
    quiz: Quiz,
    user_id: int,
    day_utc: date,
    chosen_index: int,
) -> AttemptResult:
    """
    Creates a QuizAttempt exactly once (unique constraint: quiz_id + user_id).
    If already attempted -> returns already_attempted=True.
    """
    # quick bounds check
    option_count = len(quiz.options or [])
    if chosen_index < 0 or chosen_index >= option_count:
        raise ValueError("Invalid option index")

    is_correct = chosen_index == quiz.correct_option_index
    points_awarded = quiz.points_correct if is_correct else quiz.points_wrong

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=user_id,
        day_utc=day_utc,
        chosen_index=chosen_index,
        is_correct=1 if is_correct else 0,
        points_awarded=points_awarded,
    )
    session.add(attempt)

    try:
        await session.flush()  # may raise IntegrityError if duplicate attempt
    except IntegrityError:
        await session.rollback()
        existing = await get_attempt(session, quiz.id, user_id)
        # existing should exist; if not, treat as already attempted anyway
        if existing:
            return AttemptResult(
                already_attempted=True,
                is_correct=bool(existing.is_correct),
                points_awarded=int(existing.points_awarded or 0),
                chosen_index=int(existing.chosen_index),
            )
        return AttemptResult(
            already_attempted=True,
            is_correct=False,
            points_awarded=0,
            chosen_index=chosen_index,
        )

    return AttemptResult(
        already_attempted=False,
        is_correct=is_correct,
        points_awarded=points_awarded,
        chosen_index=chosen_index,
    )
