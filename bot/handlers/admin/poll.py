# bot/handlers/admin/poll.py
from __future__ import annotations

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.auth import AuthService
from bot.services.polls import PollService, CreatePollInput

router = Router()


def _parse_poll_command(text: str) -> tuple[int | None, datetime, int, str, list[str]]:
    """
    /poll_schedule <chat_id> | <YYYY-MM-DD HH:MM UTC> | <points> | <question> | <opt1> | <opt2> | ...
    OR
    /poll_schedule <YYYY-MM-DD HH:MM UTC> | <points> | <question> | <opt1> | <opt2> | ...  (uses GROUP_ID)
    """
    raw = (text or "").split(maxsplit=1)
    if len(raw) < 2:
        raise ValueError(
            "Usage:\n"
            "A) /poll_schedule <chat_id> | <YYYY-MM-DD HH:MM UTC> | <points> | <question> | <opt1> | <opt2> ...\n"
            "B) /poll_schedule <YYYY-MM-DD HH:MM UTC> | <points> | <question> | <opt1> | <opt2> ... (uses GROUP_ID)"
        )

    parts = [p.strip() for p in raw[1].split("|") if p.strip()]

    chat_id: int | None = None
    if parts:
        first = parts[0]
        try:
            maybe = int(first)
            if str(maybe).startswith("-100") or maybe <= -1000000000:
                chat_id = maybe
                parts = parts[1:]
        except Exception:
            pass

    if len(parts) < 5:
        raise ValueError("Need: YYYY-MM-DD HH:MM (UTC) | points | question | opt1 | opt2 ...")

    when_utc = datetime.strptime(parts[0], "%Y-%m-%d %H:%M")
    points = int(parts[1])
    question = parts[2]
    options = parts[3:]
    return chat_id, when_utc, points, question, options


async def require_admin_or_reply(message: Message, settings: Settings, session: AsyncSession):
    tg = message.from_user
    if not tg:
        await message.answer("⛔ You are not allowed to use admin commands.")
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
        await message.answer("⛔ You are not allowed to use admin commands.")
        return None

    return authz


@router.message(Command("poll_schedule"))
async def cmd_poll_schedule(message: Message, settings: Settings, session: AsyncSession) -> None:
    authz = await require_admin_or_reply(message, settings, session)
    if not authz:
        return

    try:
        parsed_chat_id, when_utc, points, question, options = _parse_poll_command(message.text or "")
        chat_id = int(parsed_chat_id) if parsed_chat_id is not None else int(settings.group_id)

        poll = await PollService.create_scheduled(
            session,
            CreatePollInput(
                chat_id=chat_id,
                scheduled_for_utc=when_utc,
                question=question,
                options=options,
                points=points,
                created_by_admin_id=getattr(authz, "user_id", None) or getattr(authz, "db_user_id", None),
            ),
        )
        await session.commit()

    except Exception as e:
        await message.reply("❌ " + hd.quote(str(e)))
        return

    await message.reply(
        "✅ Poll scheduled\n"
        f"• ID: {poll.id}\n"
        f"• Chat: {poll.chat_id}\n"
        f"• When (UTC): {poll.scheduled_for_utc}\n"
        f"• Points: {poll.points}\n"
        f"• Status: {poll.status}"
    )