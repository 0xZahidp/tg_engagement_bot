from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, WeeklyUserStats


def week_start_utc(day_utc: date) -> date:
    return day_utc - timedelta(days=day_utc.weekday())


@dataclass(frozen=True, slots=True)
class LeaderRow:
    user_id: int
    telegram_id: int
    points: int
    username: str | None
    first_name: str | None
    last_name: str | None


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
    rows = []
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
    Returns (rank, points). rank is 1-based. If user has no row -> (None, 0).
    """
    # user points
    res = await session.execute(
        select(WeeklyUserStats.points).where(
            WeeklyUserStats.week_start == week_start,
            WeeklyUserStats.user_id == user_id,
        )
    )
    points = res.scalar_one_or_none()
    if points is None:
        return (None, 0)

    # rank = number of users with strictly higher points + 1
    # Tie-breaker: if equal points, earlier updated_at ranks higher; if equal updated_at, lower user_id ranks higher.
    # For simplicity, we compute rank in two steps with subqueries.
    me = await session.execute(
        select(WeeklyUserStats.points, WeeklyUserStats.updated_at, WeeklyUserStats.user_id).where(
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
