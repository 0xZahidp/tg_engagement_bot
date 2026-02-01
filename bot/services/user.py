# bot/services/user.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User


class UserService:
    @staticmethod
    async def get_or_create_from_telegram(
        session: AsyncSession,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> User:
        q = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(q)
        user = res.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

        # Update profile fields if changed (keep DB fresh)
        changed = False
        if user.username != username:
            user.username = username
            changed = True
        if user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if user.last_name != last_name:
            user.last_name = last_name
            changed = True

        if changed:
            await session.commit()
            await session.refresh(user)

        return user
