# bot/database/repo/screenshot_repo.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ScreenshotSubmission, ScreenshotStatus, User


@dataclass(frozen=True, slots=True)
class SubmissionWithUser:
    submission: ScreenshotSubmission
    user: User


def _utc_now_naive() -> datetime:
    # store in DB as naive UTC (timezone=False columns)
    return datetime.now(tz=ZoneInfo("UTC")).replace(tzinfo=None)


async def get_submission_for_day(
    session: AsyncSession, *, user_id: int, day_utc: date
) -> ScreenshotSubmission | None:
    q = select(ScreenshotSubmission).where(
        ScreenshotSubmission.user_id == user_id,
        ScreenshotSubmission.day_utc == day_utc,
    )
    res = await session.execute(q)
    return res.scalar_one_or_none()


async def create_submission_once(
    session: AsyncSession,
    *,
    user_id: int,
    day_utc: date,
    platform_uid: str,
    image_file_id: str,
    group_chat_id: int | None = None,
    group_message_id: int | None = None,
) -> tuple[bool, ScreenshotSubmission]:
    """
    Creates exactly one submission per (user_id, day_utc).
    Returns (created, submission).
    """
    existing = await get_submission_for_day(session, user_id=user_id, day_utc=day_utc)
    if existing:
        return False, existing

    sub = ScreenshotSubmission(
        user_id=user_id,
        day_utc=day_utc,
        platform_uid=platform_uid,
        image_file_id=image_file_id,
        status=ScreenshotStatus.PENDING,
        group_chat_id=group_chat_id,
        group_message_id=group_message_id,
    )
    session.add(sub)
    await session.flush()  # sub.id ready
    return True, sub


async def get_submission_with_user(session: AsyncSession, submission_id: int) -> SubmissionWithUser | None:
    q = (
        select(ScreenshotSubmission, User)
        .join(User, User.id == ScreenshotSubmission.user_id)
        .where(ScreenshotSubmission.id == submission_id)
    )
    res = await session.execute(q)
    row = res.first()
    if not row:
        return None
    sub, user = row
    return SubmissionWithUser(submission=sub, user=user)


async def assign_to_admin(
    session: AsyncSession,
    *,
    submission_id: int,
    admin_user_id: int,
    admin_chat_id: int,
    admin_message_id: int,
    expires_at_utc: datetime | None = None,
) -> bool:
    """
    Assigns submission to an admin only if it's still PENDING and unassigned.
    Returns True if assignment happened.
    """
    stmt = (
        update(ScreenshotSubmission)
        .where(
            ScreenshotSubmission.id == submission_id,
            ScreenshotSubmission.status == ScreenshotStatus.PENDING,
            ScreenshotSubmission.assigned_admin_user_id.is_(None),
        )
        .values(
            assigned_admin_user_id=admin_user_id,
            assigned_at_utc=_utc_now_naive(),
            admin_chat_id=admin_chat_id,
            admin_message_id=admin_message_id,
            expires_at_utc=expires_at_utc,
        )
    )
    res = await session.execute(stmt)
    return (res.rowcount or 0) > 0


async def decide_submission(
    session: AsyncSession,
    *,
    submission_id: int,
    decided_by_admin_user_id: int,
    status: ScreenshotStatus,  # APPROVED or REJECTED
    decision_note: str | None = None,
) -> bool:
    """
    Decides only if currently PENDING.
    Returns True if updated (decision applied), False otherwise.
    """
    if status not in (ScreenshotStatus.APPROVED, ScreenshotStatus.REJECTED):
        raise ValueError("status must be APPROVED or REJECTED")

    stmt = (
        update(ScreenshotSubmission)
        .where(
            ScreenshotSubmission.id == submission_id,
            ScreenshotSubmission.status == ScreenshotStatus.PENDING,
        )
        .values(
            status=status,
            decided_by_admin_user_id=decided_by_admin_user_id,
            decided_at_utc=_utc_now_naive(),
            decision_note=decision_note,
        )
    )
    res = await session.execute(stmt)
    return (res.rowcount or 0) > 0


async def set_admin_post_meta(
    session: AsyncSession,
    *,
    submission_id: int,
    admin_chat_id: int,
    admin_message_id: int,
) -> None:
    await session.execute(
        update(ScreenshotSubmission)
        .where(ScreenshotSubmission.id == submission_id)
        .values(admin_chat_id=admin_chat_id, admin_message_id=admin_message_id)
    )
    await session.flush()


# ✅ NEW: save approved screenshot post meta (main group message id)
async def set_group_post_meta(
    session: AsyncSession,
    *,
    submission_id: int,
    group_chat_id: int,
    group_message_id: int,
) -> None:
    await session.execute(
        update(ScreenshotSubmission)
        .where(ScreenshotSubmission.id == submission_id)
        .values(group_chat_id=int(group_chat_id), group_message_id=int(group_message_id))
    )
    await session.flush()


async def claim_submission(
    session: AsyncSession,
    *,
    submission_id: int,
    admin_user_id: int,
    ttl_minutes: int,
) -> bool:
    """
    Claim if:
    - status is PENDING or EXPIRED
    - and (unassigned OR expired OR assigned but expired)
    """
    now = _utc_now_naive()
    expires = now + timedelta(minutes=ttl_minutes)

    stmt = (
        update(ScreenshotSubmission)
        .where(
            ScreenshotSubmission.id == submission_id,
            ScreenshotSubmission.status.in_([ScreenshotStatus.PENDING, ScreenshotStatus.EXPIRED]),
            (
                (ScreenshotSubmission.assigned_admin_user_id.is_(None))
                | (ScreenshotSubmission.expires_at_utc.is_(None))
                | (ScreenshotSubmission.expires_at_utc < now)
            ),
        )
        .values(
            status=ScreenshotStatus.PENDING,
            assigned_admin_user_id=admin_user_id,
            assigned_at_utc=now,
            expires_at_utc=expires,
        )
    )
    res = await session.execute(stmt)
    return (res.rowcount or 0) > 0


async def expire_assignments(session: AsyncSession) -> int:
    """
    Marks timed-out PENDING submissions as EXPIRED and clears assignment.
    """
    now = _utc_now_naive()
    stmt = (
        update(ScreenshotSubmission)
        .where(
            ScreenshotSubmission.status == ScreenshotStatus.PENDING,
            ScreenshotSubmission.expires_at_utc.is_not(None),
            ScreenshotSubmission.expires_at_utc < now,
        )
        .values(
            status=ScreenshotStatus.EXPIRED,
            assigned_admin_user_id=None,
            assigned_at_utc=None,
            expires_at_utc=None,
        )
    )
    res = await session.execute(stmt)
    return int(res.rowcount or 0)


async def get_queue_counts(session: AsyncSession, *, day_utc: date | None = None) -> dict[str, int]:
    """
    Quick queue stats (optionally filter by day_utc).
    """
    base = select(ScreenshotSubmission.status, func.count()).group_by(ScreenshotSubmission.status)
    if day_utc is not None:
        base = base.where(ScreenshotSubmission.day_utc == day_utc)

    res = await session.execute(base)
    rows = res.all()
    out = {s.value: int(c) for s, c in rows}
    for k in ("pending", "approved", "rejected", "expired", "canceled"):
        out.setdefault(k, 0)
    return out
