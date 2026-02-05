# bot/handlers/admin/poll_set.py
from __future__ import annotations

import json
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message
from aiogram.utils.text_decorations import html_decoration as hd
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.services.auth import AuthService
from bot.services.polls import PollService, CreatePollInput

router = Router()


def _parse_poll_set(text: str) -> tuple[int, str, list[str]]:
    # /poll_set <points> | <question> | <opt1> | <opt2> | ...
    raw = (text or "").split(maxsplit=1)
    if len(raw) < 2:
        raise ValueError("Usage: /poll_set points | question | opt1 | opt2 | ...")

    parts = [p.strip() for p in raw[1].split("|") if p.strip()]
    if len(parts) < 4:
        raise ValueError("Need: points | question | opt1 | opt2 | ...")

    points = int(parts[0])
    question = parts[1]
    options = parts[2:]
    return points, question, options


async def resolve_authz(message: Message, settings: Settings, session: AsyncSession):
    tg = message.from_user
    if not tg:
        return None
    auth = AuthService(settings)
    return await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )


@router.message(F.text.startswith("/poll_set"))
async def cmd_poll_set(message: Message, settings: Settings, session: AsyncSession) -> None:
    authz = await resolve_authz(message, settings, session)
    is_admin = bool(authz and authz.is_admin)

    try:
        points, question, options = _parse_poll_set(message.text or "")
        chat_id = int(settings.group_id)
        now = datetime.utcnow()

        # ✅ Must be in future for validation
        when = now + timedelta(seconds=1)

        poll = await PollService.create_scheduled(
            session,
            CreatePollInput(
                chat_id=chat_id,
                scheduled_for_utc=when,
                question=question,
                options=options,
                points=points,
                created_by_admin_id=(getattr(authz, "user_id", None) or getattr(authz, "db_user_id", None))
                if is_admin
                else None,
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

        # ✅ Pin only if admin (and bot has permission)
        if is_admin:
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

    if not is_admin:
        await message.reply("⚠️ You are not admin. Poll posted **without pin**.")
    else:
        await message.reply("✅ Poll posted & pinned (if bot has pin permission).")