# bot/utils/ensure_user.py
from __future__ import annotations

from aiogram.types import Message, TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.database.models.user import User
from bot.database.repo.users import upsert_user_from_event


async def ensure_user(session: AsyncSession, message: Message) -> User:
    """
    Keep compatibility for message handlers (/start etc.)
    """
    row = await upsert_user_from_event(session, message)
    if row is None:
        raise RuntimeError("Unable to ensure user: message has no from_user")
    return row


async def ensure_user_from_tg(session: AsyncSession, tg_user: TgUser) -> User:
    """
    For callback queries (where we only have Telegram User).
    """
    existing = await session.scalar(select(User).where(User.telegram_id == tg_user.id))
    if existing:
        existing.username = tg_user.username
        existing.first_name = tg_user.first_name
        existing.last_name = tg_user.last_name
        return existing

    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    session.add(user)
    await session.flush()  # ensures user.id exists
    return user
