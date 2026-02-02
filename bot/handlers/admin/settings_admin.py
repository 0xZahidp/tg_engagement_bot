from __future__ import annotations

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.repo.config_repo import (
    get_config,
    set_screenshot_enabled,
    set_screenshot_points,
    set_screenshot_ttl_minutes,
)
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


def _kb(cfg) -> InlineKeyboardMarkup:
    toggle_label = "🟢 Screenshot ON" if cfg.screenshot_enabled else "🔴 Screenshot OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_label, callback_data="cfg:ss:toggle")],
            [
                InlineKeyboardButton(text="➖ Points", callback_data="cfg:ss:points:-1"),
                InlineKeyboardButton(text="➕ Points", callback_data="cfg:ss:points:+1"),
            ],
            [
                InlineKeyboardButton(text="➖ TTL", callback_data="cfg:ss:ttl:-5"),
                InlineKeyboardButton(text="➕ TTL", callback_data="cfg:ss:ttl:+5"),
            ],
        ]
    )


def _render(cfg) -> str:
    return (
        "⚙️ <b>Admin Settings</b>\n\n"
        f"🖼 <b>Screenshot Enabled:</b> {'YES' if cfg.screenshot_enabled else 'NO'}\n"
        f"⭐ <b>Screenshot Points:</b> {cfg.screenshot_points}\n"
        f"⏳ <b>Claim TTL (minutes):</b> {cfg.screenshot_claim_ttl_minutes}\n\n"
        "Commands:\n"
        "<code>/set_screenshot_points 15</code>\n"
        "<code>/set_screenshot_ttl 30</code>\n"
        "<code>/set_screenshot on</code> or <code>/set_screenshot off</code>\n"
    )


@router.message(F.text.in_({"/settings", "⚙️ Settings"}))
async def settings_panel(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    cfg = await get_config(session)
    await message.answer(_render(cfg), reply_markup=_kb(cfg))


@router.message(F.text.startswith("/set_screenshot_points"))
async def set_points_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Usage: <code>/set_screenshot_points 15</code>")
        return
    try:
        points = int(parts[1])
        if points < 0 or points > 1000:
            raise ValueError()
    except Exception:
        await message.answer("❌ Points must be an integer between 0 and 1000.")
        return

    await set_screenshot_points(session, points)
    await session.commit()
    cfg = await get_config(session)
    await message.answer("✅ Updated.\n\n" + _render(cfg), reply_markup=_kb(cfg))


@router.message(F.text.startswith("/set_screenshot_ttl"))
async def set_ttl_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Usage: <code>/set_screenshot_ttl 30</code>")
        return
    try:
        minutes = int(parts[1])
        if minutes < 1 or minutes > 24 * 60:
            raise ValueError()
    except Exception:
        await message.answer("❌ TTL must be an integer between 1 and 1440.")
        return

    await set_screenshot_ttl_minutes(session, minutes)
    await session.commit()
    cfg = await get_config(session)
    await message.answer("✅ Updated.\n\n" + _render(cfg), reply_markup=_kb(cfg))


@router.message(F.text.startswith("/set_screenshot"))
async def set_enabled_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    if not await require_admin_or_reply(message, settings, session):
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or parts[1].lower() not in {"on", "off"}:
        await message.answer("Usage: <code>/set_screenshot on</code> or <code>/set_screenshot off</code>")
        return

    enabled = parts[1].lower() == "on"
    await set_screenshot_enabled(session, enabled)
    await session.commit()
    cfg = await get_config(session)
    await message.answer("✅ Updated.\n\n" + _render(cfg), reply_markup=_kb(cfg))
