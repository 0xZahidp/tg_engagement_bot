from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.database.models.weekly_winner import WeeklyWinner


@dataclass(frozen=True, slots=True)
class WinnerRow:
    rank: int
    user_id: int
    points: int
    username: str | None
    first_name: str | None
    last_name: str | None


async def snapshot_exists(session: AsyncSession, week_start: date) -> bool:
    res = await session.execute(
        select(WeeklyWinner.id).where(WeeklyWinner.week_start == week_start).limit(1)
    )
    return res.scalar_one_or_none() is not None


async def save_snapshot(
    session: AsyncSession,
    *,
    week_start: date,
    winners: list[tuple[int, int]],  # [(user_id, points), ...] rank implied 1..n
    overwrite: bool = False,
) -> None:
    """
    Saves snapshot rows for week_start.
    If overwrite=False and snapshot already exists, does nothing.
    """
    exists = await snapshot_exists(session, week_start)
    if exists and not overwrite:
        return

    if overwrite:
        await session.execute(delete(WeeklyWinner).where(WeeklyWinner.week_start == week_start))

    rows = []
    for i, (user_id, points) in enumerate(winners[:3], start=1):
        rows.append(
            WeeklyWinner(
                week_start=week_start,
                rank=i,
                user_id=user_id,
                points=int(points or 0),
            )
        )

    session.add_all(rows)
    await session.flush()


async def get_snapshot_with_users(session: AsyncSession, week_start: date) -> list[WinnerRow]:
    q = (
        select(
            WeeklyWinner.rank,
            WeeklyWinner.user_id,
            WeeklyWinner.points,
            User.username,
            User.first_name,
            User.last_name,
        )
        .join(User, User.id == WeeklyWinner.user_id)
        .where(WeeklyWinner.week_start == week_start)
        .order_by(WeeklyWinner.rank.asc())
    )
    res = await session.execute(q)

    out: list[WinnerRow] = []
    for rank, user_id, points, username, first_name, last_name in res.all():
        out.append(
            WinnerRow(
                rank=int(rank),
                user_id=int(user_id),
                points=int(points or 0),
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
        )
    return out
