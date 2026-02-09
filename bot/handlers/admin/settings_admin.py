from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.models import PointSource, ScreenshotStatus, User
from bot.database.repo.config_repo import get_config
from bot.database.repo.points_repo import award_points_once
from bot.database.repo.screenshot_repo import (
    claim_submission,
    decide_submission,
    get_submission_with_user,
)
from bot.services.auth import AuthService
from bot.services.task_progress import TaskProgressService

log = logging.getLogger(__name__)
router = Router()


def _utc_now_naive() -> datetime:
    return datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None)


def _kb(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧑‍⚖️ Claim", callback_data=f"ss:claim:{submission_id}")],
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"ss:approve:{submission_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"ss:reject:{submission_id}"),
            ],
        ]
    )


def _is_expired(expires_at_utc: datetime | None) -> bool:
    if not expires_at_utc:
        return False
    return expires_at_utc < _utc_now_naive()


def _display_name(u: User) -> str:
    name = " ".join([p for p in [u.first_name, u.last_name] if p and str(p).strip()])
    return name.strip() or "Unknown"


def _mention_html(u: User) -> str:
    return f'<a href="tg://user?id={u.telegram_id}">{_display_name(u)}</a>'


def _admin_label(u: User) -> str:
    if u.username:
        return f"@{u.username}"
    return _mention_html(u)


async def _admin_user(session: AsyncSession, settings: Settings, cb: CallbackQuery) -> User | None:
    """
    ✅ FIX:
    - Always create/get User row first (even if ROOT admin)
    - Then check admin permission
    - Return the DB User object (needed for admin_user.id in claim/decide)
    """
    tg = cb.from_user
    if not tg:
        return None

    auth = AuthService(settings)

    # ✅ ensure User row exists for any admin clicking buttons
    user = await auth.get_or_create_user_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )

    authz = await auth.resolve(session, user)
    if not authz.is_admin:
        return None

    return user


@router.callback_query(F.data.startswith("ss:"))
async def screenshot_review_action(
    cb: CallbackQuery,
    settings: Settings,
    session: AsyncSession,
    bot,
) -> None:
    # always answer callback quickly
    try:
        await cb.answer()
    except Exception:
        pass

    if not cb.data:
        return

    admin_user = await _admin_user(session, settings, cb)
    if not admin_user:
        # better UX: alert instead of spamming chat
        try:
            await cb.answer("⛔ You are not allowed.", show_alert=True)
        except Exception:
            pass
        return

    # Parse: ss:<action>:<submission_id>
    parts = cb.data.split(":")
    if len(parts) != 3:
        return

    _, action, sid_s = parts
    try:
        submission_id = int(sid_s)
    except ValueError:
        return

    pack = await get_submission_with_user(session, submission_id)
    if not pack:
        if cb.message:
            await cb.message.answer("ℹ️ Submission not found.")
        return

    sub = pack.submission
    user = pack.user

    # Keep buttons alive (claim works after expiry)
    if cb.message:
        try:
            await cb.message.edit_reply_markup(reply_markup=_kb(submission_id))
        except Exception:
            pass

    # Load config (DB-backed)
    cfg = await get_config(session)
    ttl = int(cfg.screenshot_claim_ttl_minutes)
    points = int(cfg.screenshot_points)

    # If screenshots are disabled, block actions
    if not cfg.screenshot_enabled:
        if cb.message:
            await cb.message.answer("🚫 Screenshot review is currently disabled by admins.")
        return

    # -----------------------
    # 1) CLAIM
    # -----------------------
    if action == "claim":
        ok = await claim_submission(
            session,
            submission_id=submission_id,
            admin_user_id=admin_user.id,
            ttl_minutes=ttl,
        )
        if not ok:
            await session.rollback()
            if cb.message:
                # show a more helpful message
                await cb.message.answer(
                    "ℹ️ Already claimed by another admin (or not claimable). "
                    "Wait until it expires, then try again."
                )
            return

        await session.commit()

        if cb.message:
            await cb.message.answer(f"✅ Claimed by you. Please approve/reject within {ttl} minutes.")
        return

    # For approve/reject: must be claimed by this admin and not expired
    if sub.assigned_admin_user_id != admin_user.id or _is_expired(sub.expires_at_utc):
        if cb.message:
            await cb.message.answer("⚠️ You must claim this submission first (or it expired). Tap 🧑‍⚖️ Claim.")
        return

    # -----------------------
    # 2) APPROVE
    # -----------------------
    if action == "approve":
        ok = await decide_submission(
            session,
            submission_id=submission_id,
            decided_by_admin_user_id=admin_user.id,
            status=ScreenshotStatus.APPROVED,
            decision_note=None,
        )
        if not ok:
            await session.rollback()
            if cb.message:
                await cb.message.answer("ℹ️ Already reviewed.")
            return

        award = await award_points_once(
            session,
            user_id=sub.user_id,
            day_utc=sub.day_utc,
            source=PointSource.SCREENSHOT,
            points=points,
            ref_type="screenshot",
            ref_id=submission_id,
        )

        await TaskProgressService.mark_done(
            session,
            user_id=sub.user_id,
            day_utc=sub.day_utc,
            action_type="screenshot",
        )
        await session.commit()

        pts_awarded = points if award.awarded else 0

        # Update admin-review message UI
        if cb.message:
            try:
                await cb.message.edit_caption((cb.message.caption or "") + "\n\n✅ <b>APPROVED</b>")
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        # Send message in REVIEW GROUP
        if cb.message:
            try:
                await cb.message.answer(
                    f"✅ Screenshot approved by <b>{_admin_label(admin_user)}</b>",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        # Notify user (DM)
        try:
            extra = "" if award.awarded else " (already credited)"
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"✅ Your screenshot was approved! +{pts_awarded} points{extra}.",
            )
        except Exception:
            log.exception("Failed to notify user approval")

        # Post approved screenshot to MAIN GROUP (+ points + name + optional username)
        main_group_id = settings.group_id
        if main_group_id:
            uname = f"@{user.username}" if user.username else ""
            mention = _mention_html(user)

            caption = (
                "✅ <b>Approved Screenshot</b>\n\n"
                f"👤 <b>User:</b> {mention}"
                + (f"\n🔗 <b>Username:</b> {uname}" if uname else "")
                + f"\n⭐ <b>Points:</b> {pts_awarded}"
                + f"\n🗓 <b>Day (UTC):</b> {sub.day_utc.isoformat()}"
            )

            try:
                await bot.send_photo(
                    chat_id=main_group_id,
                    photo=sub.image_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            except Exception:
                log.exception("Failed to post approved screenshot to main group")

        return

    # -----------------------
    # 3) REJECT
    # -----------------------
    if action == "reject":
        ok = await decide_submission(
            session,
            submission_id=submission_id,
            decided_by_admin_user_id=admin_user.id,
            status=ScreenshotStatus.REJECTED,
            decision_note=None,
        )
        if not ok:
            await session.rollback()
            if cb.message:
                await cb.message.answer("ℹ️ Already reviewed.")
            return

        await session.commit()

        if cb.message:
            try:
                await cb.message.edit_caption((cb.message.caption or "") + "\n\n❌ <b>REJECTED</b>")
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        # Ensure user gets rejection DM
        try:
            await bot.send_message(chat_id=user.telegram_id, text="❌ Your screenshot was rejected.")
        except Exception:
            log.exception("Failed to notify user rejection")
        return

    if cb.message:
        await cb.message.answer("❌ Unknown action.")