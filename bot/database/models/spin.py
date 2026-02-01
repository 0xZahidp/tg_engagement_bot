# bot/database/models/spin.py
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
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


class SpinRewardType(str, enum.Enum):
    NONE = "none"
    POINTS = "points"
    CASH = "cash"


class SpinHistory(Base):
    """
    One spin per user per day UTC (unique).
    Cash prize limiting is later enforced using queries + constraints.
    """
    __tablename__ = "spin_history"
    __table_args__ = (
        UniqueConstraint("user_id", "day_utc", name="uq_spin_user_day"),
        Index("ix_spin_user_week", "user_id", "week_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day_utc: Mapped[date] = mapped_column(Date, index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)

    reward_type: Mapped[SpinRewardType] = mapped_column(
        Enum(SpinRewardType, native_enum=False),
        default=SpinRewardType.NONE,
        index=True,
    )
    reward_value: Mapped[int] = mapped_column(Integer, default=0)  # points count or cents amount

    # Optional: store RNG seed / roll text for audit
    roll: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
