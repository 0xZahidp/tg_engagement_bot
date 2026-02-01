# bot/database/repo/users.py
from __future__ import annotations

from typing import Optional

from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models.user import User


def _extract_from_user(event: TelegramObject):
    """
    Best-effort extract aiogram `from_user` from different update types.
    Works for Message, CallbackQuery, InlineQuery, etc.
    """
    # Many aiogram event objects have `.from_user`
    u = getattr(event, "from_user", None)
    if u:
        return u

    # Some nested (rare) cases:
    msg = getattr(event, "message", None)
    if msg and getattr(msg, "from_user", None):
        return msg.from_user

    cb = getattr(event, "callback_query", None)
    if cb and getattr(cb, "from_user", None):
        return cb.from_user

    return None


async def upsert_user_from_event(session: AsyncSession, event: TelegramObject) -> Optional[User]:
    tg = _extract_from_user(event)
    if tg is None:
        return None

    q = select(User).where(User.telegram_id == tg.id)
    res = await session.execute(q)
    user = res.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name,
            last_name=tg.last_name,
        )
        session.add(user)
        await session.flush()  # ensures `user.id` exists before handlers use it
        return user

    # Update fields if changed (keeps DB fresh)
    user.username = tg.username
    user.first_name = tg.first_name
    user.last_name = tg.last_name
    return user


async def get_user_with_admin(session: AsyncSession, telegram_id: int) -> Optional[User]:
    q = (
        select(User)
        .options(selectinload(User.admin))
        .where(User.telegram_id == telegram_id)
    )
    res = await session.execute(q)
    return res.scalar_one_or_none()
