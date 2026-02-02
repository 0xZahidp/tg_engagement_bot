from __future__ import annotations

from datetime import date, datetime
from enum import Enum  # ✅ Python Enum

from sqlalchemy import Date, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class DailyActionType(str, Enum):
    CHECKIN = "checkin"
    QUIZ = "quiz"
    SCREENSHOT = "screenshot"
    SPIN = "spin"
    POLL_VOTE = "poll_vote"  # completion when poll closes & points granted


class DailyAction(Base):
    __tablename__ = "daily_actions"
    __table_args__ = (
        UniqueConstraint("user_id", "day_utc", "action_type", name="uq_daily_action_user_day_type"),
        Index("ix_daily_action_day_type", "day_utc", "action_type"),
        Index("ix_daily_action_user_day", "user_id", "day_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day_utc: Mapped[date] = mapped_column(Date, index=True)

    # keep stored as a string (no migrations needed)
    action_type: Mapped[str] = mapped_column(index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
