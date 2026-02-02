# bot/database/models/quiz.py
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class Quiz(Base):
    """
    One quiz per day in UTC (enforced by unique day_utc).
    """
    __tablename__ = "quizzes"
    __table_args__ = (
        UniqueConstraint("day_utc", name="uq_quizzes_day_utc"),
        Index("ix_quizzes_day_utc", "day_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    day_utc: Mapped[date] = mapped_column(Date, index=True)

    question: Mapped[str] = mapped_column(String(512))
    correct_option_index: Mapped[int] = mapped_column(Integer)  # 0..n-1

    points_correct: Mapped[int] = mapped_column(Integer, default=10)
    points_wrong: Mapped[int] = mapped_column(Integer, default=0)

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())

    options: Mapped[list["QuizOption"]] = relationship(
        "QuizOption",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizOption.index",
    )


class QuizOption(Base):
    __tablename__ = "quiz_options"
    __table_args__ = (
        UniqueConstraint("quiz_id", "index", name="uq_quiz_options_quiz_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)

    index: Mapped[int] = mapped_column(Integer)  # 0..n-1
    text: Mapped[str] = mapped_column(String(256))

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="options")


class QuizAttempt(Base):
    """
    One attempt per user per quiz (enforced by unique constraint).
    """
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("quiz_id", "user_id", name="uq_quiz_attempts_quiz_user"),
        Index("ix_quiz_attempts_user_day", "user_id", "day_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    day_utc: Mapped[date] = mapped_column(Date, index=True)

    chosen_index: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Integer, default=0)  # sqlite bool
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
