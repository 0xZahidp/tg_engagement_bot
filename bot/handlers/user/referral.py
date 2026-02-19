#bot/handlers/user/referral.py
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.models import PointEvent, PointSource, User
from bot.database.repo.points_repo import award_points_once
from bot.keyboards.main import BTN_REFERRAL
from bot.utils.ensure_user import ensure_user
from bot.utils.reply import reply_safe

log = logging.getLogger(__name__)
router = Router()

REFERRAL_CAP = 100  # lifetime successful referrals cap


def _utc_today():
    return datetime.now(tz=ZoneInfo("UTC")).date()


async def _referral_count(session: AsyncSession, *, user_id: int) -> int:
    """Counts successful referrals using the point ledger (source=referral)."""
    count = await session.scalar(
        select(func.count(PointEvent.id)).where(
            PointEvent.user_id == user_id,
            PointEvent.source == PointSource.REFERRAL,
        )
    )
    return int(count or 0)


async def _send_referral_info(message: Message, session: AsyncSession, settings: Settings) -> None:
    me = await ensure_user(session, message)
    link = f"https://t.me/{settings.bot_username}?start=ref_{me.telegram_id}"

    total = await _referral_count(session, user_id=me.id)
    remaining = max(0, REFERRAL_CAP - total)

    # ✅ Join main group button (Option A)
    join_kb = None
    if settings.group_invite_link:
        join_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Join Main Group", url=settings.group_invite_link)]
            ]
        )

    await reply_safe(
        message,
        "👥 <b>Your referral link</b>\n"
        f"{link}\n\n"
        f"✅ <b>Successful referrals:</b> {total}\n"
        f"🎯 <b>Remaining until cap ({REFERRAL_CAP}):</b> {remaining}\n\n"
        "✅ <b>How it works:</b>\n"
        "1️⃣ Share this referral link\n"
        "2️⃣ Friend must press <b>Start</b> in bot\n"
        "3️⃣ Friend joins the main group using the button below\n\n"
        "When they join, you get <b>+1 point</b> 🎉",
        reply_markup=join_kb,
    )


@router.message(Command("ref"))
async def ref_cmd(message: Message, session: AsyncSession, settings: Settings) -> None:
    await _send_referral_info(message, session, settings)


@router.message(F.text == BTN_REFERRAL)
async def ref_btn(message: Message, session: AsyncSession, settings: Settings) -> None:
    await _send_referral_info(message, session, settings)


@router.chat_member()
async def referral_join_award(
    event: ChatMemberUpdated,
    session: AsyncSession,
    settings: Settings,
) -> None:
    # Must have group_id set
    if not settings.group_id:
        return

    # Only main group
    if event.chat.id != settings.group_id:
        return

    # ✅ The user whose membership changed (NOT event.from_user)
    changed_user = event.new_chat_member.user
    if not changed_user:
        return

    old = event.old_chat_member.status
    new = event.new_chat_member.status

    # join detection (left/kicked -> member/admin/creator)
    joined = (old in ("left", "kicked")) and (new in ("member", "administrator", "creator"))
    if not joined:
        return

    tg_id = changed_user.id
    log.info("Referral join update: tg_id=%s old=%s new=%s chat=%s", tg_id, old, new, event.chat.id)

    user = await session.scalar(select(User).where(User.telegram_id == tg_id))
    if not user:
        log.info("Referral join: user not found in DB tg_id=%s", tg_id)
        return

    # Already handled this user's referral join
    if user.referral_processed:
        log.info("Referral join: already processed tg_id=%s", tg_id)
        return

    # No referrer attached
    if not user.referred_by_user_id:
        log.info("Referral join: no referrer tg_id=%s", tg_id)
        user.referral_processed = True
        await session.flush()
        return

    referrer = await session.scalar(select(User).where(User.id == user.referred_by_user_id))
    if not referrer:
        log.info("Referral join: referrer missing tg_id=%s referred_by_user_id=%s", tg_id, user.referred_by_user_id)
        user.referral_processed = True
        await session.flush()
        return

    # Cap check for referrer
    current_count = await _referral_count(session, user_id=referrer.id)
    log.info("Referral join: referrer=%s current_count=%s", referrer.telegram_id, current_count)

    if current_count >= REFERRAL_CAP:
        log.info("Referral join: cap reached referrer=%s", referrer.telegram_id)
        user.referral_processed = True
        await session.flush()
        return

    # ✅ Award exactly once per referred user via ledger uniqueness
    res = await award_points_once(
        session,
        user_id=referrer.id,
        day_utc=_utc_today(),
        source=PointSource.REFERRAL,
        points=1,
        ref_type="referral",
        ref_id=user.id,
    )

    # Mark processed regardless of duplicate attempt
    user.referral_processed = True
    await session.flush()

    log.info("Referral award: awarded=%s referrer=%s referred_tg=%s", res.awarded, referrer.telegram_id, tg_id)

    if res.awarded:
        try:
            await event.bot.send_message(
                chat_id=referrer.telegram_id,
                text="🎉 You earned +1 point from a referral join!",
            )
        except Exception:
            pass