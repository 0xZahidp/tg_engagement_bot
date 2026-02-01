# bot/services/checkin.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import DailyActionType, DailyCheckin, PointSource, WeeklyUserStats
from bot.database.tx import transactional
from bot.services.points import PointsService
from bot.services.task_progress import TaskProgressService
from bot.utils.dates import week_start_monday


@dataclass(frozen=True, slots=True)
class CheckinResult:
    ok: bool
    already: bool
    points_awarded: int
    week_points: int
    week_streak: int


class CheckinService:
    BASE_POINTS = 2

    @staticmethod
    async def checkin(session: AsyncSession, *, user_id: int, day_utc: date) -> CheckinResult:
        week_start = week_start_monday(day_utc)
        yesterday = day_utc - timedelta(days=1)

        # 1) Hard anti-abuse: unique (user_id, day_utc)
        try:
            async with transactional(session):
                session.add(DailyCheckin(user_id=user_id, day_utc=day_utc))
                await session.flush()
        except IntegrityError:
            # Already checked in today
            await session.rollback()

            # Backfill daily action marker (idempotent)
            await TaskProgressService.mark_done(
                session,
                user_id=user_id,
                day_utc=day_utc,
                action_type=DailyActionType.CHECKIN,
            )

            res = await session.execute(
                select(WeeklyUserStats).where(
                    WeeklyUserStats.week_start == week_start,
                    WeeklyUserStats.user_id == user_id,
                )
            )
            ws = res.scalar_one_or_none()

            return CheckinResult(
                ok=True,
                already=True,
                points_awarded=0,
                week_points=int(ws.points) if ws else 0,
                week_streak=int(ws.checkin_streak) if ws else 0,
            )

        # 2) Mark daily action done
        await TaskProgressService.mark_done(
            session,
            user_id=user_id,
            day_utc=day_utc,
            action_type=DailyActionType.CHECKIN,
        )

        # 3) Determine streak from weekly stats
        res = await session.execute(
            select(WeeklyUserStats).where(
                WeeklyUserStats.week_start == week_start,
                WeeklyUserStats.user_id == user_id,
            )
        )
        ws = res.scalar_one_or_none()

        if ws and ws.last_checkin_day == yesterday:
            new_streak = int(ws.checkin_streak or 0) + 1
        else:
            new_streak = 1

        # 4) Award points + update weekly stats
        applied = await PointsService.add_points(
            session,
            user_id=user_id,
            week_start=week_start,
            day_utc=day_utc,
            source=PointSource.CHECKIN,
            points=CheckinService.BASE_POINTS,
            ref_type="checkin",
            ref_id=int(day_utc.strftime("%Y%m%d")),
            new_last_checkin_day=day_utc,
            new_checkin_streak=new_streak,
        )

        return CheckinResult(
            ok=True,
            already=False,
            points_awarded=CheckinService.BASE_POINTS,
            week_points=applied.new_week_points,
            week_streak=applied.week_streak,
        )
