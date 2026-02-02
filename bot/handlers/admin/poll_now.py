# bot/handlers/admin/poll_now.py
from __future__ import annotations

import json
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.auth import AuthService
from bot.services.polls import PollService, CreatePollInput

router = Router()


def _parse_poll_now(text: str) -> tuple[int | None, int, str, list[str]]:
    """
    Supports:
    A) /poll_now <chat_id> | <points> | <question> | <opt1> | <opt2> | ...
    B) /poll_now <points> | <question> | <opt1> | <opt2> | ... (uses settings.group_id)
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
        raise ValueError("Need: points | question | opt1 | opt2 ...  (or chat_id | points | question | opt1 | opt2 ...)")

    # detect chat_id if first part looks like int and starts with -100... or digits
    chat_id: int | None = None
    first = parts[0]
    if first.startswith("-") or first.isdigit():
        # could be chat_id or could be points
        # decide: if it starts with -100 or is very large negative => it's chat_id
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


@router.message(F.text.startswith("/poll_now"))
async def poll_now_cmd(message: Message, settings: Settings, session: AsyncSession) -> None:
    authz = await require_admin_or_reply(message, settings, session)
    if not authz:
        return

    try:
        parsed_chat_id, points, question, options = _parse_poll_now(message.text or "")
        chat_id = int(parsed_chat_id) if parsed_chat_id is not None else int(settings.group_id)

        now = datetime.utcnow()

        # Create DB poll, then post immediately and mark posted
        poll = await PollService.create_scheduled(
            session,
            CreatePollInput(
                chat_id=chat_id,
                scheduled_for_utc=now,  # immediate
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

        # Pin (ignore permission failures)
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
        # Escape error to avoid HTML parse crashes
        await message.reply("❌ " + hd.quote(str(e)))
        return

    await message.answer(
        "✅ <b>Poll posted now</b>\n"
        f"• Poll ID: <code>{poll.id}</code>\n"
        f"• Chat: <code>{poll.chat_id}</code>\n"
        f"• Points: <b>{poll.points}</b>\n"
        "• It will auto-close after 24h and then award points.",
        parse_mode="HTML",
    )
