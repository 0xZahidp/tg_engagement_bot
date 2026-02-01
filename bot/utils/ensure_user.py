from __future__ import annotations

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.services.user import UserService


async def ensure_user(session: AsyncSession, message: Message) -> User:
    tg_user = message.from_user
    if tg_user is None:
        raise RuntimeError("Missing from_user in message")

    return await UserService.get_or_create_from_telegram(
        session=session,
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
