# bot/database/models/points.py
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class PointSource(str, enum.Enum):
    CHECKIN = "checkin"
    QUIZ = "quiz"
    POLL = "poll"
    SCREENSHOT = "screenshot"
    SPIN = "spin"
    ADMIN_ADJUST = "admin_adjust"


class WeeklyUserStats(Base):
    """
    One row per user per week. This enables fast leaderboards.
    week_start is UTC week boundary (Monday).
    """
    __tablename__ = "weekly_user_stats"
    __table_args__ = (
        UniqueConstraint("week_start", "user_id", name="uq_weekly_user_stats_week_user"),
        Index("ix_weekly_user_stats_week_points", "week_start", "points"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    points: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # streak support for /checkin
    checkin_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_checkin_day: Mapped[date | None] = mapped_column(Date, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PointEvent(Base):
    """
    Immutable ledger of point additions. Great for audit + admin verification.
    """
    __tablename__ = "point_events"
    __table_args__ = (
        Index("ix_point_events_week_user", "week_start", "user_id"),
        Index("ix_point_events_day_user", "day_utc", "user_id"),

        # ✅ Anti-duplicate award protection:
        # Callers must pass meaningful (ref_type, ref_id) for sources like quiz/poll/screenshot/spin.
        # For checkin, pass ref_type="checkin" and ref_id=YYYYMMDD integer.
        UniqueConstraint("user_id", "source", "ref_type", "ref_id", name="uq_point_events_user_src_ref"),

        # Optional sanity constraint
        CheckConstraint("points != 0", name="ck_point_events_points_nonzero"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    week_start: Mapped[date] = mapped_column(Date, index=True)
    day_utc: Mapped[date] = mapped_column(Date, index=True)

    source: Mapped[PointSource] = mapped_column(Enum(PointSource, native_enum=False), index=True)
    points: Mapped[int] = mapped_column(Integer)

    # link back to originating entity (quiz_id, poll_id, submission_id, etc.)
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
