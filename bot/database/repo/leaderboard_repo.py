from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, WeeklyUserStats, PointEvent


# ------------------------
# Week helpers (unchanged)
# ------------------------

def week_start_utc(day_utc: date) -> date:
    # Monday-based (legacy, still used for storage)
    return day_utc - timedelta(days=day_utc.weekday())


# ------------------------
# Shared row DTO
# ------------------------

@dataclass(frozen=True, slots=True)
class LeaderRow:
    user_id: int
    telegram_id: int
    points: int
    username: str | None
    first_name: str | None
    last_name: str | None


# =========================================================
# WEEKLY LEADERBOARD (UNCHANGED – BACKWARD COMPATIBLE)
# =========================================================

async def get_top_week(
    session: AsyncSession,
    week_start: date,
    limit: int = 10,
) -> list[LeaderRow]:
    q = (
        select(
            WeeklyUserStats.user_id,
            WeeklyUserStats.points,
            User.telegram_id,
            User.username,
            User.first_name,
            User.last_name,
        )
        .join(User, User.id == WeeklyUserStats.user_id)
        .where(WeeklyUserStats.week_start == week_start)
        .order_by(
            desc(WeeklyUserStats.points),
            WeeklyUserStats.updated_at.asc(),
            WeeklyUserStats.user_id.asc(),
        )
        .limit(limit)
    )

    res = await session.execute(q)
    rows: list[LeaderRow] = []

    for user_id, points, telegram_id, username, first_name, last_name in res.all():
        rows.append(
            LeaderRow(
                user_id=int(user_id),
                telegram_id=int(telegram_id),
                points=int(points or 0),
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )

    return rows


async def get_user_rank_week(
    session: AsyncSession,
    week_start: date,
    user_id: int,
) -> tuple[int | None, int]:
    """
    Weekly rank (storage-based).
    Returns (rank, points). rank is 1-based.
    """

    res = await session.execute(
        select(WeeklyUserStats.points).where(
            WeeklyUserStats.week_start == week_start,
            WeeklyUserStats.user_id == user_id,
        )
    )
    points = res.scalar_one_or_none()
    if points is None:
        return (None, 0)

    me = await session.execute(
        select(
            WeeklyUserStats.points,
            WeeklyUserStats.updated_at,
            WeeklyUserStats.user_id,
        ).where(
            WeeklyUserStats.week_start == week_start,
            WeeklyUserStats.user_id == user_id,
        )
    )
    me_row = me.first()
    if not me_row:
        return (None, int(points or 0))

    me_points, me_updated_at, me_user_id = me_row

    higher = await session.execute(
        select(WeeklyUserStats.user_id).where(
            WeeklyUserStats.week_start == week_start,
            (
                (WeeklyUserStats.points > me_points)
                | (
                    (WeeklyUserStats.points == me_points)
                    & (WeeklyUserStats.updated_at < me_updated_at)
                )
                | (
                    (WeeklyUserStats.points == me_points)
                    & (WeeklyUserStats.updated_at == me_updated_at)
                    & (WeeklyUserStats.user_id < me_user_id)
                )
            ),
        )
    )

    rank = len(higher.all()) + 1
    return (rank, int(points or 0))


# =========================================================
# RANGE / CAMPAIGN LEADERBOARD (NEW)
# =========================================================

async def get_top_range(
    session: AsyncSession,
    start: date,
    end: date,
    limit: int = 10,
) -> list[LeaderRow]:
    """
    Campaign or arbitrary date-range leaderboard.
    Uses PointEvent ledger (authoritative).
    """

    q = (
        select(
            PointEvent.user_id,
            func.sum(PointEvent.points).label("points"),
            User.telegram_id,
            User.username,
            User.first_name,
            User.last_name,
        )
        .join(User, User.id == PointEvent.user_id)
        .where(PointEvent.day_utc.between(start, end))
        .group_by(
            PointEvent.user_id,
            User.telegram_id,
            User.username,
            User.first_name,
            User.last_name,
        )
        .order_by(desc(func.sum(PointEvent.points)))
        .limit(limit)
    )

    res = await session.execute(q)
    rows: list[LeaderRow] = []

    for user_id, points, telegram_id, username, first_name, last_name in res.all():
        rows.append(
            LeaderRow(
                user_id=int(user_id),
                telegram_id=int(telegram_id),
                points=int(points or 0),
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )

    return rows


async def get_user_rank_range(
    session: AsyncSession,
    start: date,
    end: date,
    user_id: int,
) -> tuple[int | None, int]:
    """
    Rank within a campaign/date range.
    """

    totals = (
        select(
            PointEvent.user_id,
            func.sum(PointEvent.points).label("points"),
        )
        .where(PointEvent.day_utc.between(start, end))
        .group_by(PointEvent.user_id)
        .subquery()
    )

    me = await session.execute(
        select(totals.c.points).where(totals.c.user_id == user_id)
    )
    my_points = me.scalar_one_or_none()

    if my_points is None:
        return (None, 0)

    higher = await session.execute(
        select(totals.c.user_id).where(totals.c.points > my_points)
    )

    rank = len(higher.all()) + 1
    return (rank, int(my_points))
