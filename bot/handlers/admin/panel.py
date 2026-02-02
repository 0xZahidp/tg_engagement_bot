# bot/handlers/admin/panel.py
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
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


@router.message(F.text == "⚙️ Settings")
async def open_settings(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return
    # import here to avoid circular imports
    from bot.handlers.admin.settings_admin import settings_panel
    await settings_panel(message, settings, session)


@router.message(F.text == "🧠 Quiz Admin")
async def open_quiz_admin(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return
    from bot.handlers.admin.quiz_admin import quiz_admin_panel
    await quiz_admin_panel(message, settings, session)


@router.message(F.text == "🖼 Screenshot Admin")
async def open_screenshot_admin(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return
    # If you don’t have a panel yet, at least show help
    await message.answer(
        "🖼 <b>Screenshot Admin</b>\n\n"
        "Use the review group buttons to Claim/Approve/Reject.\n"
        "Queue panel will be added next step."
    )


@router.message(F.text == "📊 Poll Admin")
async def open_poll_admin(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return
    await message.answer(
        "📊 <b>Poll Admin</b>\n\n"
        "Poll system not implemented yet. Next step we will add:\n"
        "<code>/poll_set \"Question\" | \"A\" | \"B\" | points=5</code>"
    )
