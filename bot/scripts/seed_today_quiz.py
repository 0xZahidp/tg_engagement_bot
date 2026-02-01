# bot/scripts/seed_today_quiz.py
from __future__ import annotations

import asyncio
from sqlalchemy import delete, select

from bot.config import settings
from bot.database.session import Database
from bot.database.models import Quiz, QuizOption
from bot.utils.dates import utc_today


async def main() -> None:
    db = Database(settings.database_url)
    await db.init_models()

    day = utc_today()

    async with db.session() as session:
        # If quiz already exists today, delete it (options first)
        existing_q = await session.execute(select(Quiz).where(Quiz.day_utc == day))
        existing = existing_q.scalar_one_or_none()
        if existing:
            await session.execute(delete(QuizOption).where(QuizOption.quiz_id == existing.id))
            await session.execute(delete(Quiz).where(Quiz.id == existing.id))
            await session.commit()

        # Options order is the "index" used by correct_option_index
        options = [
            ("Risk-to-Reward ratio", True),
            ("Rate-to-Rate indicator", False),
            ("Return-to-Return metric", False),
        ]

        correct_index = next((i for i, (_, is_ok) in enumerate(options) if is_ok), None)
        if correct_index is None:
            raise RuntimeError("Seed quiz has no correct option!")

        quiz = Quiz(
            day_utc=day,
            question="What does 'R:R' mean in trading?",
            correct_option_index=correct_index,  # ✅ NOT NULL
            points_correct=10,
            points_wrong=0,
            created_by_admin_id=None,  # keep None only if your column allows NULL
        )
        session.add(quiz)
        await session.flush()  # quiz.id available now

        session.add_all(
            [
                QuizOption(quiz_id=quiz.id, index=i, text=text)
                for i, (text, _is_ok) in enumerate(options)
            ]
        )


        await session.commit()

    await db.close()
    print("✅ Seeded today's quiz.")


if __name__ == "__main__":
    asyncio.run(main())
