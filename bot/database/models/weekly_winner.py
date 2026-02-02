from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class WeeklyWinner(Base):
    """
    Immutable snapshot of weekly winners.
    One row per (week_start, rank).
    """
    __tablename__ = "weekly_winners"
    __table_args__ = (
        UniqueConstraint("week_start", "rank", name="uq_weekly_winners_week_rank"),
        Index("ix_weekly_winners_week", "week_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    week_start: Mapped[date] = mapped_column(Date, index=True)
    rank: Mapped[int] = mapped_column(Integer)  # 1..3

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    points: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
