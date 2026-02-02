# bot/scheduler/jobs.py
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
from bot.database.repo.leaderboard_repo import get_top_week
from bot.database.repo.weekly_winners_repo import (
    get_snapshot_with_users,
    save_snapshot,
    snapshot_exists,
)
from bot.utils.cards.weekly_winners_card import CardWinner, render_weekly_winners_card
from bot.database.repo.screenshot_repo import expire_assignments

log = logging.getLogger(__name__)


def _utc_today() -> date:
    return datetime.now(tz=ZoneInfo("UTC")).date()


def week_start_utc(day_utc: date) -> date:
    # Monday boundary
    return day_utc - timedelta(days=day_utc.weekday())


def _display_name(username: str | None, first_name: str | None, last_name: str | None) -> str:
    if username:
        return f"@{username}"
    name = " ".join([p for p in [first_name, last_name] if p])
    return name.strip() or "User"


async def post_weekly_winners(bot: Bot, db, settings: Settings, *, mode: str = "previous") -> None:
    """
    Posts top 3 winners into settings.group_id.

    mode:
      - "previous" (default): last completed week (Mon-Sun UTC) ✅ production
      - "current": current week so far ✅ testing
    """
    if not settings.group_id:
        log.warning("Skipping weekly winners post: GROUP_ID is not set")
        return

    today = _utc_today()
    this_week = week_start_utc(today)

    if mode == "current":
        target_week = this_week
        week_end = today  # so far (today)
        title = "Weekly Winners (Current Week • Test)"
    else:
        # default = previous completed week
        target_week = this_week - timedelta(days=7)
        week_end = this_week - timedelta(days=1)
        title = "Weekly Winners"

    async def _run(session: AsyncSession):
        # Snapshot if missing (for that target week)
        if not await snapshot_exists(session, target_week):
            top3 = await get_top_week(session, target_week, limit=3)
            winners = [(r.user_id, r.points) for r in top3]
            await save_snapshot(session, week_start=target_week, winners=winners, overwrite=False)
            await session.commit()

        return await get_snapshot_with_users(session, target_week)

    # Open DB session
    if callable(getattr(db, "session", None)):
        async with db.session() as session:
            snap = await _run(session)
    else:
        sessionmaker = getattr(db, "sessionmaker", None) or getattr(db, "async_sessionmaker", None)
        if sessionmaker is None:
            raise RuntimeError("Database object has no session() or sessionmaker/async_sessionmaker")
        async with sessionmaker() as session:
            snap = await _run(session)

    # If no winners, fallback text
    if not snap:
        await bot.send_message(
            chat_id=settings.group_id,
            text=(
                f"🏆 <b>{title}</b>\n"
                f"📅 <b>Week (UTC):</b> {target_week.isoformat()} → {week_end.isoformat()}\n\n"
                "ℹ️ No points were earned for this period."
            ),
        )
        return

    winners_for_card: list[CardWinner] = []
    for row in snap:
        name = _display_name(row.username, row.first_name, row.last_name)
        winners_for_card.append(CardWinner(rank=row.rank, name=name, points=row.points))

    png_bytes = render_weekly_winners_card(
        week_start=target_week,
        week_end=week_end,
        winners=winners_for_card,
        title=title,
    )

    photo = BufferedInputFile(png_bytes, filename=f"weekly_winners_{target_week.isoformat()}_{mode}.png")

    caption = (
        f"🏆 <b>{title}</b>\n"
        f"📅 <b>Week (UTC):</b> {target_week.isoformat()} → {week_end.isoformat()}\n\n"
        "🔥 Keep grinding!"
    )

    await bot.send_photo(chat_id=settings.group_id, photo=photo, caption=caption)

def build_scheduler(bot: Bot, db, settings: Settings) -> AsyncIOScheduler:
    """
    Creates and returns an AsyncIOScheduler with our jobs registered.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # ✅ Production: Every Monday 00:05 UTC
    trigger = CronTrigger(day_of_week="mon", hour=0, minute=5, timezone="UTC")

    # ✅ Dev/Test (uncomment temporarily):
    # trigger = CronTrigger(minute="*/1", timezone="UTC")

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

