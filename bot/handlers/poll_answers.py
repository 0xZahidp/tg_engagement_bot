# bot/handlers/poll_answers.py
from __future__ import annotations

from aiogram import Router
from aiogram.types import PollAnswer
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.polls import PollService

router = Router()


@router.poll_answer()
async def on_poll_answer(event: PollAnswer, session: AsyncSession) -> None:
    poll = await PollService.get_by_telegram_poll_id(session, event.poll_id)
    if not poll:
        return
    if poll.status != "posted":
        return
    if not event.option_ids:
        return

    option_index = int(event.option_ids[0])
    user_id = int(event.user.id)

    await PollService.record_vote_first_only(
        session,
        poll_id=poll.id,
        user_id=user_id,
        option_index=option_index,
    )
