# bot/database/models/admin.py
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base


class AdminRole(str, enum.Enum):
    ROOT = "root"
    ADMIN = "admin"


class Admin(Base):
    __tablename__ = "admins"
    __table_args__ = (UniqueConstraint("user_id", name="uq_admins_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, native_enum=False),
        default=AdminRole.ADMIN,
        index=True,
    )

    # Optional label (like “Mr X”) if you want to store it explicitly
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="admin")
