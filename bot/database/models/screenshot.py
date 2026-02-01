# bot/database/models/screenshot.py
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


class ScreenshotStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"       # timed-out and will be reassigned
    CANCELED = "canceled"


class ScreenshotSubmission(Base):
    """
    One submission per user per day UTC (unique).
    Assigned to exactly one admin at a time.
    """
    __tablename__ = "screenshot_submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "day_utc", name="uq_screenshot_user_day"),
        Index("ix_screenshot_status_assigned", "status", "assigned_admin_user_id"),
        Index("ix_screenshot_day_status", "day_utc", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day_utc: Mapped[date] = mapped_column(Date, index=True)

    platform_uid: Mapped[str] = mapped_column(String(64))
    image_file_id: Mapped[str] = mapped_column(String(256))  # Telegram file_id

    status: Mapped[ScreenshotStatus] = mapped_column(
        Enum(ScreenshotStatus, native_enum=False),
        default=ScreenshotStatus.PENDING,
        index=True,
    )

    # assignment (admin is a user)
    assigned_admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    expires_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    # transparency posts
    group_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    admin_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # decision
    decided_by_admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decided_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
