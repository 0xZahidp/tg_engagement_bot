# bot/services/polls.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Poll, PollVote, PointSource
from bot.database.tx import transactional
from bot.services.points import PointsService


@dataclass(frozen=True)
class CreatePollInput:
    chat_id: int
    scheduled_for_utc: datetime
    question: str
    options: list[str]
    points: int
    created_by_admin_id: int | None


def _week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class PollService:
    CLOSE_AFTER = timedelta(hours=24)

    @staticmethod
    def _normalize_options(options: list[str]) -> list[str]:
        return [str(o).strip() for o in options if str(o).strip()]

    @staticmethod
    async def create_scheduled(session: AsyncSession, inp: CreatePollInput) -> Poll:
        q = (inp.question or "").strip()
        opts = PollService._normalize_options(inp.options)

        if not (5 <= len(q) <= 300):
            raise ValueError("Question must be 5..300 characters.")
        if not (2 <= len(opts) <= 10):
            raise ValueError("Options must be 2..10 items.")
        if any(len(o) > 100 for o in opts):
            raise ValueError("Each option must be <= 100 characters.")
        if inp.points < 0 or inp.points > 100:
            raise ValueError("Points must be between 0 and 100.")
        if inp.scheduled_for_utc <= datetime.utcnow():
            raise ValueError("scheduled_for_utc must be in the future (UTC).")

        poll = Poll(
            chat_id=inp.chat_id,
            scheduled_for_utc=inp.scheduled_for_utc,
            question=q,
            options_json=json.dumps(opts, ensure_ascii=False),
            points=inp.points,
            created_by_admin_id=inp.created_by_admin_id,
            status="scheduled",
        )

        async with transactional(session):
            session.add(poll)
            await session.flush()
            await session.refresh(poll)

        return poll

    @staticmethod
    async def list_due_to_post(session: AsyncSession, now_utc: datetime, limit: int = 20) -> list[Poll]:
        stmt = (
            select(Poll)
            .where(Poll.status == "scheduled", Poll.scheduled_for_utc <= now_utc)
            .order_by(Poll.scheduled_for_utc.asc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_posted(
        session: AsyncSession,
        *,
        poll_id: int,
        telegram_poll_id: str,
        message_id: int,
        posted_at_utc: datetime,
    ) -> None:
        closes_at = posted_at_utc + PollService.CLOSE_AFTER
        async with transactional(session):
            stmt = (
                update(Poll)
                .where(Poll.id == poll_id, Poll.status == "scheduled")
                .values(
                    status="posted",
                    telegram_poll_id=telegram_poll_id,
                    message_id=message_id,
                    posted_at_utc=posted_at_utc,
                    closes_at_utc=closes_at,
                )
            )
            await session.execute(stmt)

    @staticmethod
    async def get_by_telegram_poll_id(session: AsyncSession, telegram_poll_id: str) -> Poll | None:
        stmt = select(Poll).where(Poll.telegram_poll_id == telegram_poll_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def record_vote_first_only(
        session: AsyncSession,
        *,
        poll_id: int,
        user_id: int,
        option_index: int,
    ) -> bool:
        try:
            async with transactional(session):
                session.add(PollVote(poll_id=poll_id, user_id=user_id, option_index=option_index))
                await session.flush()
            return True
        except IntegrityError:
            await session.rollback()
            return False

    @staticmethod
    async def list_due_to_close(session: AsyncSession, now_utc: datetime, limit: int = 20) -> list[Poll]:
        stmt = (
            select(Poll)
            .where(
                Poll.status == "posted",
                Poll.closes_at_utc.is_not(None),
                Poll.closes_at_utc <= now_utc,
            )
            .order_by(Poll.closes_at_utc.asc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def mark_closed(session: AsyncSession, *, poll_id: int) -> None:
        async with transactional(session):
            stmt = (
                update(Poll)
                .where(Poll.id == poll_id, Poll.status == "posted")
                .values(status="closed")
            )
            await session.execute(stmt)

    @staticmethod
    async def award_points_after_close(session: AsyncSession, *, poll_id: int, now_utc: datetime) -> int:
        poll = await session.get(Poll, poll_id)
        if not poll or poll.status != "closed":
            return 0
        if poll.points_awarded_at_utc is not None:
            return 0

        if poll.points <= 0:
            async with transactional(session):
                poll.points_awarded_at_utc = now_utc
                await session.flush()
            return 0

        stmt = select(PollVote.user_id).where(PollVote.poll_id == poll_id)
        res = await session.execute(stmt)
        voter_ids = [int(x) for x in res.scalars().all()]

        day_utc = now_utc.date()
        week_start = _week_start_monday(day_utc)

        newly_awarded = 0
        for uid in voter_ids:
            r = await PointsService.add_points(
                session,
                user_id=uid,
                week_start=week_start,
                day_utc=day_utc,
                source=PointSource.POLL,
                points=poll.points,
                ref_type="poll",
                ref_id=poll.id,
            )
            if r.awarded:
                newly_awarded += 1

        async with transactional(session):
            poll.points_awarded_at_utc = now_utc
            await session.flush()

        return newly_awarded
