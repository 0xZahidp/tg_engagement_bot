# bot/services/points.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from bot.database.models import PointEvent, PointSource, WeeklyUserStats
from bot.database.tx import transactional


@dataclass(frozen=True, slots=True)
class PointsApplyResult:
    awarded: bool
    new_week_points: int
    week_streak: int


class PointsService:
    @staticmethod
    async def add_points(
        session: AsyncSession,
        *,
        user_id: int,
        week_start: date,
        day_utc: date,
        source: PointSource,
        points: int,
        ref_type: str | None = None,
        ref_id: int | None = None,
        new_last_checkin_day: date | None = None,
        new_checkin_streak: int | None = None,
    ) -> PointsApplyResult:
        """
        Award points exactly once (duplicate-safe using PointEvent unique constraint).
        Returns awarded=False if this award already exists.
        """
        points = int(points)

        async with transactional(session):
            # 1) Try to write ledger event FIRST (so duplicates do not increment weekly stats)
            session.add(
                PointEvent(
                    user_id=user_id,
                    week_start=week_start,
                    day_utc=day_utc,
                    source=source,
                    points=points,
                    ref_type=ref_type,
                    ref_id=ref_id,
                )
            )

            try:
                await session.flush()  # triggers uq constraint check
            except IntegrityError:
                # Duplicate award attempt
                await session.rollback()

                # Fetch current stats to return stable values
                res = await session.execute(
                    select(WeeklyUserStats).where(
                        WeeklyUserStats.week_start == week_start,
                        WeeklyUserStats.user_id == user_id,
                    )
                )
                ws = res.scalar_one_or_none()
                return PointsApplyResult(
                    awarded=False,
                    new_week_points=int(ws.points) if ws else 0,
                    week_streak=int(ws.checkin_streak) if ws else 0,
                )

            # 2) Upsert weekly stats atomically (SQLite ON CONFLICT)
            stmt = sqlite_insert(WeeklyUserStats).values(
                week_start=week_start,
                user_id=user_id,
                points=points,
                checkin_streak=(new_checkin_streak or 0),
                last_checkin_day=new_last_checkin_day,
            ).on_conflict_do_update(
                index_elements=["week_start", "user_id"],
                set_={
                    "points": WeeklyUserStats.points + points,
                    # only update streak fields if provided
                    "checkin_streak": (
                        new_checkin_streak if new_checkin_streak is not None else WeeklyUserStats.checkin_streak
                    ),
                    "last_checkin_day": (
                        new_last_checkin_day if new_last_checkin_day is not None else WeeklyUserStats.last_checkin_day
                    ),
                },
            )
            await session.execute(stmt)

            # 3) Load updated stats
            res = await session.execute(
                select(WeeklyUserStats).where(
                    WeeklyUserStats.week_start == week_start,
                    WeeklyUserStats.user_id == user_id,
                )
            )
            ws = res.scalar_one()

            return PointsApplyResult(
                awarded=True,
                new_week_points=int(ws.points),
                week_streak=int(ws.checkin_streak or 0),
            )
