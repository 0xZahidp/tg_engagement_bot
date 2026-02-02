# bot/database/models/app_config.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class AppConfig(Base):
    """
    Single-row config table.
    Keep bot_token, group ids in ENV.
    Keep gameplay/task settings here.
    """
    __tablename__ = "app_config"

    id: Mapped[int] = mapped_column(primary_key=True)  # always 1

    screenshot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    screenshot_points: Mapped[int] = mapped_column(Integer, default=15)
    screenshot_claim_ttl_minutes: Mapped[int] = mapped_column(Integer, default=30)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )
