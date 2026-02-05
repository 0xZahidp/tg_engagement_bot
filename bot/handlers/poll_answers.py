# bot/handlers/poll_answers.py
from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.types import PollAnswer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User  # ✅ your SQLAlchemy User model
from bot.services.polls import PollService

router = Router()


async def get_or_create_db_user(session: AsyncSession, tg_user) -> User:
    """
    PollAnswer doesn't go through your upsert_user_from_event reliably.
    So we ensure a DB user row exists here.
    """
    stmt = select(User).where(User.telegram_id == int(tg_user.id))
    res = await session.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        # keep username updated (optional)
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        return user

    user = User(
        telegram_id=int(tg_user.id),
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    session.add(user)
    await session.flush()
    return user


@router.poll_answer()
async def on_poll_answer(event: PollAnswer, session: AsyncSession) -> None:
    poll = await PollService.get_by_telegram_poll_id(session, event.poll_id)
    if not poll or poll.status != "posted":
        return
    if not event.option_ids:
        return

    now = datetime.utcnow()
    db_user = await get_or_create_db_user(session, event.user)
    db_user_id = int(db_user.id)

    option_index = int(event.option_ids[0])

    inserted = await PollService.record_vote_first_only(
        session,
        poll_id=poll.id,
        user_id=db_user_id,   # ✅ DB user id
        option_index=option_index,
    )

    if inserted:
        await PollService.award_points_on_vote(
            session,
            poll_id=poll.id,
            user_id=db_user_id,
            now_utc=now,
        )

    # middleware auto-commits, so no need to session.commit() here