# bot/services/auth.py
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Settings
from bot.database.models import Admin, AdminRole, User


@dataclass(frozen=True, slots=True)
class AuthResult:
    is_root: bool
    is_admin: bool
    role: str  # "root" | "admin" | "user"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def resolve(self, session: AsyncSession, user: User) -> AuthResult:
        # Root admins come from env, always takes precedence.
        if user.telegram_id in self.settings.root_admin_ids:
            return AuthResult(is_root=True, is_admin=True, role="root")

        q = select(Admin).where(Admin.user_id == user.id)
        res = await session.execute(q)
        admin = res.scalar_one_or_none()

        if admin is None:
            return AuthResult(is_root=False, is_admin=False, role="user")

        # DB admins are general admins for now
        return AuthResult(
            is_root=False,
            is_admin=True,
            role="admin" if admin.role == AdminRole.ADMIN else "admin",
        )
