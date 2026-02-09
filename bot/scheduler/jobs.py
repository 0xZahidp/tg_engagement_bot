from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.repo.leaderboard_repo import (
    get_top_week,
    get_top_range,
)
from bot.database.repo.weekly_winners_repo import (
    get_snapshot_with_users,
    save_snapshot,
    snapshot_exists,
)
from bot.utils.cards.weekly_winners_card import CardWinner, render_weekly_winners_card
from bot.database.repo.screenshot_repo import expire_assignments
from bot.utils.leaderboard_window import resolve_leaderboard_window

log = logging.getLogger(__name__)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def _utc_today() -> date:
    return datetime.now(tz=ZoneInfo("UTC")).date()


def week_start_utc(day_utc: date) -> date:
    # Monday boundary (legacy weekly storage)
    return day_utc - timedelta(days=day_utc.weekday())


def _display_name(username: str | None, first_name: str | None, last_name: str | None) -> str:
    if username:
        return f"@{username}"
    name = " ".join([p for p in [first_name, last_name] if p])
    return name.strip() or "User"


# -------------------------------------------------
# Main job: post winners
# -------------------------------------------------

async def post_weekly_winners(
    bot: Bot,
    db,
    settings: Settings,
    *,
    mode: str | None = None,  # ✅ backward compatibility
) -> None:
    """
    Posts winners into settings.group_id.

    Priority:
    1️⃣ Campaign ending today → snapshot + announce ONCE
    2️⃣ Otherwise → normal weekly (Sunday-based)

    NOTE:
    - `mode` is accepted for backward compatibility
    - Campaign logic ALWAYS takes precedence
    """

    if mode:
        log.info("post_weekly_winners called with legacy mode=%s (ignored)", mode)

    if not settings.group_id:
        log.warning("Skipping winners post: GROUP_ID is not set")
        return

    today = _utc_today()
    window = resolve_leaderboard_window(today)

    # =================================================
    # 🟢 CASE 1: Campaign just ended → announce once
    # =================================================
    if window.kind == "campaign" and today == window.end:
        target_start = window.start
        target_end = window.end
        title = "🏆 Campaign Winners"

        async def _run(session: AsyncSession):
            if not await snapshot_exists(session, target_start):
                top3 = await get_top_range(session, target_start, target_end, limit=3)
                winners = [(r.user_id, r.points) for r in top3]
                await save_snapshot(
                    session,
                    week_start=target_start,  # reuse column safely
                    winners=winners,
                    overwrite=False,
                )
                await session.commit()

            return await get_snapshot_with_users(session, target_start)

    # =================================================
    # 🔵 CASE 2: Normal weekly flow (Sunday-based)
    # =================================================
    else:
        # Announce PREVIOUS completed week
        this_week = week_start_utc(today)
        target_start = this_week - timedelta(days=7)
        target_end = this_week - timedelta(days=1)
        title = "Weekly Winners"

        async def _run(session: AsyncSession):
            if not await snapshot_exists(session, target_start):
                top3 = await get_top_week(session, target_start, limit=3)
                winners = [(r.user_id, r.points) for r in top3]
                await save_snapshot(
                    session,
                    week_start=target_start,
                    winners=winners,
                    overwrite=False,
                )
                await session.commit()

            return await get_snapshot_with_users(session, target_start)

    # -------------------------------------------------
    # DB session handling
    # -------------------------------------------------

    if callable(getattr(db, "session", None)):
        async with db.session() as session:
            snap = await _run(session)
    else:
        sessionmaker = getattr(db, "sessionmaker", None) or getattr(db, "async_sessionmaker", None)
        if sessionmaker is None:
            raise RuntimeError("Database object has no session() or sessionmaker/async_sessionmaker")
        async with sessionmaker() as session:
            snap = await _run(session)

    # -------------------------------------------------
    # No winners fallback
    # -------------------------------------------------

    if not snap:
        await bot.send_message(
            chat_id=settings.group_id,
            text=(
                f"🏆 <b>{title}</b>\n"
                f"📅 <b>Period (UTC):</b> {target_start.isoformat()} → {target_end.isoformat()}\n\n"
                "ℹ️ No points were earned for this period."
            ),
        )
        return

    # -------------------------------------------------
    # Render & send card
    # -------------------------------------------------

    winners_for_card: list[CardWinner] = []
    for row in snap:
        name = _display_name(row.username, row.first_name, row.last_name)
        winners_for_card.append(
            CardWinner(rank=row.rank, name=name, points=row.points)
        )

    png_bytes = render_weekly_winners_card(
        week_start=target_start,
        week_end=target_end,
        winners=winners_for_card,
        title=title,
    )

    photo = BufferedInputFile(
        png_bytes,
        filename=f"winners_{target_start.isoformat()}.png",
    )

    caption = (
        f"🏆 <b>{title}</b>\n"
        f"📅 <b>Period (UTC):</b> {target_start.isoformat()} → {target_end.isoformat()}\n\n"
        "🔥 Keep grinding!"
    )

    await bot.send_photo(
        chat_id=settings.group_id,
        photo=photo,
        caption=caption,
    )


# -------------------------------------------------
# Scheduler setup
# -------------------------------------------------

def build_scheduler(bot: Bot, db, settings: Settings) -> AsyncIOScheduler:
    """
    Creates and returns an AsyncIOScheduler with our jobs registered.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # ✅ Production: Every Sunday 00:05 UTC
    scheduler.add_job(
        post_weekly_winners,
        trigger=CronTrigger(day_of_week="sun", hour=0, minute=5, timezone="UTC"),
        kwargs={"bot": bot, "db": db, "settings": settings},
        id="post_weekly_winners",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=300,
    )

    scheduler.add_job(
        expire_screenshot_assignments,
        trigger=CronTrigger(minute="*/1", timezone="UTC"),
        kwargs={"db": db},
        id="expire_screenshot_assignments",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=60,
    )

    return scheduler


# -------------------------------------------------
# Screenshot expiry
# -------------------------------------------------

async def expire_screenshot_assignments(db) -> None:
    async def _run(session: AsyncSession):
        n = await expire_assignments(session)
        if n:
            await session.commit()

    if callable(getattr(db, "session", None)):
        async with db.session() as session:
            await _run(session)
    else:
        sessionmaker = getattr(db, "sessionmaker", None) or getattr(db, "async_sessionmaker", None)
        if sessionmaker is None:
            raise RuntimeError("Database object has no session() or sessionmaker/async_sessionmaker")
        async with sessionmaker() as session:
            await _run(session)
