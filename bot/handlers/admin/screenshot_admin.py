from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
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


async def _admin_user(session: AsyncSession, settings: Settings, cb: CallbackQuery) -> User | None:
    tg = cb.from_user
    if not tg:
        return None

    auth = AuthService(settings)
    authz = await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )
    if not authz.is_admin:
        return None

    res = await session.execute(select(User).where(User.telegram_id == tg.id))
    return res.scalar_one_or_none()


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
        if cb.message:
            await cb.message.answer("⛔ You are not allowed to use admin commands.")
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
                await cb.message.answer("ℹ️ Already claimed (or not claimable).")
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

        if cb.message:
            try:
                await cb.message.edit_caption((cb.message.caption or "") + "\n\n✅ <b>APPROVED</b>")
                await cb.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        try:
            pts = points if award.awarded else 0
            extra = "" if award.awarded else " (already credited)"
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"✅ Your screenshot was approved! +{pts} points{extra}.",
            )
        except Exception:
            log.exception("Failed to notify user approval")
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

        try:
            await bot.send_message(chat_id=user.telegram_id, text="❌ Your screenshot was rejected.")
        except Exception:
            log.exception("Failed to notify user rejection")
        return

    # Unknown action
    if cb.message:
        await cb.message.answer("❌ Unknown action.")
