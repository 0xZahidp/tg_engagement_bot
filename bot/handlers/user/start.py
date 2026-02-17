from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.models.user import User
from bot.utils.ensure_user import ensure_user
from bot.utils.reply import reply_safe

router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message, session: AsyncSession, settings: Settings) -> None:
    me = await ensure_user(session, message)

    # payload format: /start ref_<telegram_id>
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    payload = parts[1].strip() if len(parts) > 1 else ""

    # Only set referrer once (don't overwrite existing)
    if payload.startswith("ref_") and not me.referred_by_user_id:
        try:
            ref_tg_id = int(payload[4:].strip())  # remove "ref_"
        except ValueError:
            ref_tg_id = 0

        # Block invalid/self referral
        if ref_tg_id and ref_tg_id != me.telegram_id:
            referrer = await session.scalar(select(User).where(User.telegram_id == ref_tg_id))
            if referrer:
                me.referred_by_user_id = referrer.id
                # Do NOT set referral_processed here (only after group join)
                await session.flush()

    # 1) Show join group link (inline button)
    if settings.group_invite_link:
        join_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Join Main Group", url=settings.group_invite_link)]
            ]
        )
        await message.answer(
            "✅ Welcome!\nTap below to join the main group:",
            reply_markup=join_kb,
        )

    # 2) Show menu keyboard
    await reply_safe(
        message,
        "Use the menu buttons below 👇",
    )