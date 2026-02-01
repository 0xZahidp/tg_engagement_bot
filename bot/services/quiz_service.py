# bot/services/quiz_service.py
from __future__ import annotations

from datetime import datetime, timezone, date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models.quiz import Quiz, QuizAttempt
from bot.database.models import PointSource
from bot.services.points import PointsService
from bot.utils.dates import week_start_monday


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


class QuizService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_quiz_for_day(self, day: date) -> Quiz | None:
        res = await self.session.execute(
            select(Quiz)
            .where(Quiz.day_utc == day)
            .options(selectinload(Quiz.options))
        )
        return res.scalar_one_or_none()

    async def get_today_quiz(self) -> Quiz | None:
        return await self.get_quiz_for_day(utc_today())

    async def get_attempt(self, quiz_id: int, user_id: int) -> QuizAttempt | None:
        res = await self.session.execute(
            select(QuizAttempt).where(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    async def submit_attempt(self, quiz: Quiz, user_id: int, chosen_index: int) -> QuizAttempt | None:
        # Prevent double attempt
        existing = await self.get_attempt(quiz.id, user_id)
        if existing:
            return None

        is_correct = int(chosen_index == quiz.correct_option_index)
        points = quiz.points_correct if is_correct else quiz.points_wrong

        attempt = QuizAttempt(
            quiz_id=quiz.id,
            user_id=user_id,
            day_utc=quiz.day_utc,
            chosen_index=chosen_index,
            is_correct=is_correct,
            points_awarded=int(points),
        )
        self.session.add(attempt)
        await self.session.flush()  # attempt.id available (and unique constraints checked)

        # Award points (duplicate-safe by PointEvent uq)
        ws = week_start_monday(quiz.day_utc)
        await PointsService.add_points(
            self.session,
            user_id=user_id,
            week_start=ws,
            day_utc=quiz.day_utc,
            source=PointSource.QUIZ,
            points=int(points),
            ref_type="quiz",
            ref_id=int(quiz.id),
        )

        return attempt
