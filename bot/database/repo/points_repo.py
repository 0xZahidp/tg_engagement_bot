from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import PointEvent, PointSource, WeeklyUserStats


def week_start_utc(day_utc: date) -> date:
    """
    Monday as week boundary in UTC.
    """
    return day_utc - timedelta(days=day_utc.weekday())


@dataclass(frozen=True, slots=True)
class AwardResult:
    awarded: bool
    points: int
    week_start: date


async def award_points_once(
    session: AsyncSession,
    *,
    user_id: int,
    day_utc: date,
    source: PointSource,
    points: int,
    ref_type: str,
    ref_id: int,
) -> AwardResult:
    """
    Adds an immutable PointEvent and increments WeeklyUserStats atomically.
    Protected from duplicates by uq_point_events_user_src_ref.

    Returns awarded=False if it was already awarded previously.
    """
    if points == 0:
        # Your table has CheckConstraint(points != 0), so never insert 0-point events.
        return AwardResult(awarded=False, points=0, week_start=week_start_utc(day_utc))

    ws = week_start_utc(day_utc)

    ev = PointEvent(
        user_id=user_id,
        week_start=ws,
        day_utc=day_utc,
        source=source,
        points=points,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    session.add(ev)

    try:
        await session.flush()  # may raise IntegrityError if duplicate event
    except IntegrityError:
        await session.rollback()
        return AwardResult(awarded=False, points=points, week_start=ws)

    # Upsert weekly stats row
    res = await session.execute(
        select(WeeklyUserStats).where(
            WeeklyUserStats.week_start == ws,
            WeeklyUserStats.user_id == user_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = WeeklyUserStats(week_start=ws, user_id=user_id, points=0)
        session.add(row)
        await session.flush()

    row.points = int(row.points or 0) + int(points)
    await session.flush()

    return AwardResult(awarded=True, points=points, week_start=ws)
