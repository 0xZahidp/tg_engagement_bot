from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import Settings
from bot.database.models import User
from bot.database.repo.leaderboard_repo import (
    get_top_week,
    get_user_rank_week,
    week_start_utc,
)
from bot.services.auth import AuthService
from bot.utils.reply import reply_safe

router = Router()


def _utc_today():
    return datetime.now(tz=ZoneInfo("UTC")).date()


def _display_name(username: str | None, first_name: str | None, last_name: str | None) -> str:
    if username:
        return f"@{username}"
    name = " ".join([p for p in [first_name, last_name] if p])
    return name.strip() or "User"


async def _get_or_create_user(
    session: AsyncSession, settings: Settings, message: Message
) -> User | None:
    tg = message.from_user
    if not tg:
        return None

    auth = AuthService(settings)
    await auth.resolve_by_telegram(
        session=session,
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
    )

    res = await session.execute(select(User).where(User.telegram_id == tg.id))
    return res.scalar_one_or_none()


@router.message(F.text == "🏆 Leaderboard")
@router.message(F.text == "/leaderboard")
async def leaderboard_cmd(
    message: Message, settings: Settings, session: AsyncSession
) -> None:
    user = await _get_or_create_user(session, settings, message)
    if not user:
        await reply_safe(message, "⚠️ Please try again.")
        return

    today_utc = _utc_today()
    ws = week_start_utc(today_utc)

    top = await get_top_week(session, ws, limit=10)

    lines = [
        "🏆 <b>Weekly Leaderboard</b>",
        f"📅 <b>Week starts (UTC):</b> {ws.isoformat()}",
        "",
    ]

    if not top:
        lines.append("ℹ️ No points yet this week.")
        await reply_safe(message, "\n".join(lines), parse_mode="HTML")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    my_rank_from_top: int | None = None
    my_points_from_top: int | None = None

    for i, row in enumerate(top, start=1):
        medal = medals.get(i, f"{i}.")
        name = _display_name(row.username, row.first_name, row.last_name)
        you = " <b>(you)</b>" if row.user_id == user.id else ""

        lines.append(f"{medal} {name} — <b>{row.points}</b> pts{you}")

        if row.user_id == user.id:
            my_rank_from_top = i
            my_points_from_top = int(row.points)

    repo_rank, repo_points = await get_user_rank_week(session, ws, user.id)

    lines.append("")
    if my_rank_from_top is not None:
        lines.append(
            f"📍 <b>Your rank:</b> {my_rank_from_top} / <b>{my_points_from_top}</b> pts"
        )
    else:
        if repo_rank is None:
            lines.append("📍 <b>Your rank:</b> unranked (0 pts)")
        else:
            rank_display = int(repo_rank)
            if rank_display <= 0:
                rank_display += 1
            lines.append(
                f"📍 <b>Your rank:</b> {rank_display} / <b>{int(repo_points or 0)}</b> pts"
            )

    await reply_safe(message, "\n".join(lines), parse_mode="HTML")
