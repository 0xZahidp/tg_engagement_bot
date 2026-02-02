from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models import Quiz, QuizOption


async def get_quiz_for_day(session: AsyncSession, day_utc: date) -> Quiz | None:
    q = (
        select(Quiz)
        .where(Quiz.day_utc == day_utc)
        .options(selectinload(Quiz.options))
    )
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def replace_quiz_for_day(
    session: AsyncSession,
    day_utc: date,
    question: str,
    options: list[str],
    correct_index_1based: int,
    points_correct: int = 10,
    points_wrong: int = 0,
    created_by_user_id: int | None = None,
) -> Quiz:
    """
    correct_index_1based: 1..n from command input
    Stored as 0..n-1 in Quiz.correct_option_index
    """
    existing = await get_quiz_for_day(session, day_utc)
    if existing:
        await session.execute(delete(QuizOption).where(QuizOption.quiz_id == existing.id))
        await session.execute(delete(Quiz).where(Quiz.id == existing.id))

    correct_0 = correct_index_1based - 1

    quiz = Quiz(
        day_utc=day_utc,
        question=question,
        correct_option_index=correct_0,
        points_correct=points_correct,
        points_wrong=points_wrong,
        created_by_admin_id=created_by_user_id,
    )
    session.add(quiz)
    await session.flush()  # quiz.id

    session.add_all([QuizOption(quiz_id=quiz.id, index=i, text=opt) for i, opt in enumerate(options)])
    await session.flush()
    return quiz
