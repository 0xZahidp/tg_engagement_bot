# bot/database/models/poll.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class Poll(Base):
    """
    Admin-scheduled poll.
    After posting, telegram_poll_id/message_id are stored.
    """
    __tablename__ = "polls"
    __table_args__ = (
        Index("ix_polls_scheduled_for", "scheduled_for_utc"),
        Index("ix_polls_closes_at", "closes_at_utc"),
        Index("ix_polls_telegram_poll_id", "telegram_poll_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    question: Mapped[str] = mapped_column(String(300))
    options_json: Mapped[str] = mapped_column(String(1500))  # JSON string
    points: Mapped[int] = mapped_column(Integer, default=5)

    # Telegram chat IDs are often -100..., BigInteger is correct
    chat_id: Mapped[int] = mapped_column(BigInteger)

    scheduled_for_utc: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)

    telegram_poll_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    posted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    closes_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    # ✅ ensures awarding happens only once
    points_awarded_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, index=True)

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # scheduled / posted / closed / canceled
    status: Mapped[str] = mapped_column(String(16), default="scheduled", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())


class PollVote(Base):
    """
    One vote per user per poll (unique).
    'Votes cannot be changed' enforced by unique constraint + no updates.
    """
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "user_id", name="uq_poll_votes_poll_user"),
        Index("ix_poll_votes_poll", "poll_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    poll_id: Mapped[int] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    option_index: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
