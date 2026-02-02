from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.repo.screenshot_repo import get_queue_counts
from bot.services.auth import AuthService

router = Router()


async def require_admin_or_reply(message: Message, settings: Settings, session: AsyncSession) -> bool:
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed.")
        return False
    auth = AuthService(settings)
    authz = await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )
    if not authz.is_admin:
        await message.answer("⛔ You are not allowed.")
        return False
    return True


@router.message(F.text == "/ss_queue")
async def ss_queue(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    counts = await get_queue_counts(session)
    await message.answer(
        "🗂 <b>Screenshot Queue</b>\n\n"
        f"⏳ Pending: <b>{counts['pending']}</b>\n"
        f"⌛ Expired: <b>{counts['expired']}</b>\n"
        f"✅ Approved: <b>{counts['approved']}</b>\n"
        f"❌ Rejected: <b>{counts['rejected']}</b>\n"
    )
