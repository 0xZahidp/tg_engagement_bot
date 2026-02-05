# bot/handlers/admin/poll_now.py
from __future__ import annotations

import json
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.auth import AuthService
from bot.services.polls import PollService, CreatePollInput

router = Router()


def _parse_poll_now(text: str) -> tuple[int | None, int, str, list[str]]:
    """
    A) /poll_now <chat_id> | <points> | <question> | <opt1> | <opt2> | ...
    B) /poll_now <points> | <question> | <opt1> | <opt2> | ... (uses GROUP_ID)
    """
    raw = (text or "").split(maxsplit=1)
    if len(raw) < 2:
        raise ValueError(
            "Usage:\n"
            "A) /poll_now chat_id | points | question | opt1 | opt2 ...\n"
            "B) /poll_now points | question | opt1 | opt2 ... (uses GROUP_ID)"
        )

    parts = [p.strip() for p in raw[1].split("|") if p.strip()]
    if len(parts) < 4:
        raise ValueError("Need: points | question | opt1 | opt2 ... (or chat_id | points | question | opt1 | opt2 ...)")

    chat_id: int | None = None
    first = parts[0]
    try:
        maybe = int(first)
        if str(maybe).startswith("-100") or maybe <= -1000000000:
            chat_id = maybe
            parts = parts[1:]
    except Exception:
        pass

    if len(parts) < 4:
        raise ValueError("Need: points | question | opt1 | opt2 ...")

    points = int(parts[0])
    question = parts[1]
    options = parts[2:]
    return chat_id, points, question, options


async def require_admin_or_reply(message: Message, settings: Settings, session: AsyncSession):
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed.", parse_mode="HTML")
        return None

    auth = AuthService(settings)
    authz = await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )
    if not authz.is_admin:
        await message.answer("⛔ You are not allowed.", parse_mode="HTML")
        return None

    return authz


@router.message(Command("poll_now"))
async def poll_now_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    authz = await require_admin_or_reply(message, settings, session)
    if not authz:
        return

    try:
        parsed_chat_id, points, question, options = _parse_poll_now(message.text or "")
        chat_id = int(parsed_chat_id) if parsed_chat_id is not None else int(settings.group_id)

        now = datetime.utcnow()
        when = now + timedelta(seconds=1)  # ✅ must be future for create_scheduled validation

        poll = await PollService.create_scheduled(
            session,
            CreatePollInput(
                chat_id=chat_id,
                scheduled_for_utc=when,
                question=question,
                options=options,
                points=points,
                created_by_admin_id=getattr(authz, "user_id", None) or getattr(authz, "db_user_id", None),
            ),
        )

        opts = json.loads(poll.options_json)
        msg = await message.bot.send_poll(
            chat_id=poll.chat_id,
            question=poll.question,
            options=opts,
            is_anonymous=False,
            allows_multiple_answers=False,
        )

        try:
            await message.bot.pin_chat_message(
                chat_id=poll.chat_id,
                message_id=msg.message_id,
                disable_notification=True,
            )
        except Exception:
            pass

        await PollService.mark_posted(
            session,
            poll_id=poll.id,
            telegram_poll_id=msg.poll.id,
            message_id=msg.message_id,
            posted_at_utc=now,
        )

        await session.commit()

    except Exception as e:
        await message.reply("❌ " + hd.quote(str(e)))
        return

    await message.answer(
        "✅ <b>Poll posted now</b>\n"
        f"• Poll ID: <code>{poll.id}</code>\n"
        f"• Chat: <code>{poll.chat_id}</code>\n"
        f"• Points: <b>{poll.points}</b>\n"
        "• It will auto-close after 24h.",
        parse_mode="HTML",
    )