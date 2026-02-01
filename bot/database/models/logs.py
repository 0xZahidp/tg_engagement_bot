# bot/database/models/logs.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class AdminActionLog(Base):
    """
    Log all admin actions for audit and rollback support.
    Payload is JSON string (we’ll serialize dict->json in services).
    """
    __tablename__ = "admin_action_logs"
    __table_args__ = (
        Index("ix_admin_action_logs_actor_time", "actor_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(64), index=True)     # e.g. "quiz_create", "poll_cancel", "ss_approve"
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "quiz", "poll", "submission"
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payload_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())
