from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.config.settings import Settings
from bot.database.models import User
from bot.database.repo.screenshot_repo import create_submission_once
from bot.services.auth import AuthService
from bot.database.repo.config_repo import get_config
from bot.utils.reply import reply_safe
from bot.keyboards.open_bot import open_bot_kb

log = logging.getLogger(__name__)
router = Router()


class ScreenshotStates(StatesGroup):
    waiting_photo = State()


def _utc_today():
    return datetime.now(tz=ZoneInfo("UTC")).date()


def _review_kb(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧑‍⚖️ Claim", callback_data=f"ss:claim:{submission_id}")],
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"ss:approve:{submission_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"ss:reject:{submission_id}"),
            ],
        ]
    )


async def _ensure_user(session: AsyncSession, settings: Settings, message: Message) -> User | None:
    tg = message.from_user
    if not tg:
        return None

    auth = AuthService(settings)
    await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )

    res = await session.execute(select(User).where(User.telegram_id == tg.id))
    return res.scalar_one_or_none()


@router.message(F.text.in_({"🖼 Screenshot", "/screenshot"}))
async def screenshot_entry(message: Message, state: FSMContext, settings: Settings) -> None:
    # 🚫 BLOCK FSM IN GROUPS
    if message.chat.type != "private":
        await message.answer(
            "🖼 <b>Screenshot submission is available in private chat only.</b>\n\n"
            "Please open the bot and submit your screenshot there.",
            parse_mode="HTML",
            reply_markup=open_bot_kb(settings.bot_username),
        )
        return

    # ✅ PRIVATE CHAT → FSM STARTS
    await state.set_state(ScreenshotStates.waiting_photo)
    await reply_safe(
        message,
        "🖼 <b>Screenshot Task</b>\n\n"
        "Send <b>one</b> screenshot photo now.\n"
        "✅ 1 submission per day (UTC)\n\n"
        "Cancel: /cancel",
        parse_mode="HTML",
    )


@router.message(F.text == "/cancel")
async def screenshot_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await reply_safe(message, "✅ Cancelled.")


@router.message(ScreenshotStates.waiting_photo, F.photo)
async def screenshot_receive_photo(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session: AsyncSession,
    bot,
) -> None:
    user = await _ensure_user(session, settings, message)
    if not user:
        await reply_safe(message, "⚠️ Please try again.")
        return

    photo = message.photo[-1]
    image_file_id = photo.file_id
    platform_uid = str(message.from_user.id)
    today = _utc_today()

    created, sub = await create_submission_once(
        session,
        user_id=user.id,
        day_utc=today,
        platform_uid=platform_uid,
        image_file_id=image_file_id,
        group_chat_id=message.chat.id,
        group_message_id=message.message_id,
    )

    if not created:
        await session.rollback()
        await state.clear()
        await reply_safe(message, "ℹ️ You already submitted a screenshot for today (UTC).")
        return

    await session.commit()
    await state.clear()

    cfg = await get_config(session)
    if not cfg.screenshot_enabled:
        await reply_safe(message, "ℹ️ Screenshot task is currently disabled by admins.")
        return

    review_chat_id = settings.admin_review_chat_id or settings.group_id
    if not review_chat_id:
        await reply_safe(message, "✅ Submitted, but admin review chat is not configured yet.")
        return

    caption = (
        "🖼 <b>Screenshot Review</b>\n\n"
        f"👤 <b>User:</b> @{user.username or 'unknown'}\n"
        f"🗓 <b>Day (UTC):</b> {today.isoformat()}\n"
        f"🆔 <b>Submission ID:</b> {sub.id}\n"
        f"⭐ <b>Points on approve:</b> {cfg.screenshot_points}"
    )

    try:
        m = await bot.send_photo(
            chat_id=review_chat_id,
            photo=image_file_id,
            caption=caption,
            reply_markup=_review_kb(sub.id),
            parse_mode="HTML",
        )
        from bot.database.repo.screenshot_repo import set_admin_post_meta

        await set_admin_post_meta(
            session,
            submission_id=sub.id,
            admin_chat_id=m.chat.id,
            admin_message_id=m.message_id,
        )
        await session.commit()
    except Exception:
        log.exception("Failed to send screenshot to review chat")

    await reply_safe(message, "✅ Screenshot submitted! It will be reviewed by admins.")
