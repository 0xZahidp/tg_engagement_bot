from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.scheduler.jobs import post_weekly_winners
from bot.services.auth import AuthService

router = Router()


async def require_admin_or_reply(message: Message, settings: Settings, session: AsyncSession) -> bool:
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed to use admin commands.")
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
        await message.answer("⛔ You are not allowed to use admin commands.")
        return False

    return True


@router.message(F.text == "/weekly_winners_post")
async def weekly_winners_post_cmd(
    message: Message,
    settings: Settings,
    session: AsyncSession,
    bot,
    db,
) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    await message.answer("⏳ Posting PREVIOUS week winners to the group...")
    await post_weekly_winners(bot=bot, db=db, settings=settings, mode="previous")
    await message.answer("✅ Done.")


@router.message(F.text == "/weekly_winners_post_current")
async def weekly_winners_post_current_cmd(
    message: Message,
    settings: Settings,
    session: AsyncSession,
    bot,
    db,
) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    await message.answer("⏳ Posting CURRENT week winners to the group (test)...")
    await post_weekly_winners(bot=bot, db=db, settings=settings, mode="current")
    await message.answer("✅ Done.")
