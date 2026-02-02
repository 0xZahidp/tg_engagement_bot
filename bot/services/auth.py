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

        return AuthResult(
            is_root=False,
            is_admin=True,
            role=admin.role.value,
        )

    async def get_or_create_user_by_telegram(
        self,
        session: AsyncSession,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        q = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(q)
        user = res.scalar_one_or_none()

        if user:
            # Keep data fresh (optional but useful)
            changed = False
            if username is not None and user.username != username:
                user.username = username
                changed = True
            if first_name is not None and user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if last_name is not None and user.last_name != last_name:
                user.last_name = last_name
                changed = True
            if changed:
                await session.flush()
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        session.add(user)
        await session.flush()  # user.id becomes available
        return user

    async def resolve_by_telegram(
        self,
        session: AsyncSession,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> AuthResult:
        # Root admins come from env, always takes precedence.
        if telegram_id in self.settings.root_admin_ids:
            return AuthResult(is_root=True, is_admin=True, role="root")

        user = await self.get_or_create_user_by_telegram(
            session=session,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        return await self.resolve(session, user)
