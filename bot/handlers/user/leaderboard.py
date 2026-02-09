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
    get_top_range,
    get_user_rank_range,
    week_start_utc,
)
from bot.services.auth import AuthService
from bot.utils.reply import reply_safe
from bot.utils.leaderboard_window import resolve_leaderboard_window

router = Router()


# -------------------------------------------------
# Helpers
# -------------------------------------------------

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


# -------------------------------------------------
# Leaderboard command
# -------------------------------------------------

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
    window = resolve_leaderboard_window(today_utc)

    # =================================================
    # 🟢 Campaign leaderboard (display override)
    # =================================================
    if window.kind == "campaign":
        top = await get_top_range(session, window.start, window.end, limit=10)
        my_rank, my_points = await get_user_rank_range(
            session, window.start, window.end, user.id
        )

        title = "🏆 <b>Campaign Leaderboard</b>"
        period_line = f"📅 <b>Campaign (UTC):</b> {window.start} → {window.end}"

    # =================================================
    # 🔵 Weekly leaderboard (default)
    # =================================================
    else:
        ws = week_start_utc(today_utc)
        top = await get_top_week(session, ws, limit=10)
        my_rank, my_points = await get_user_rank_week(session, ws, user.id)

        title = "🏆 <b>Weekly Leaderboard</b>"
        period_line = f"📅 <b>Week starts (UTC):</b> {ws.isoformat()}"

    # -------------------------------------------------
    # Build response
    # -------------------------------------------------

    lines = [
        title,
        period_line,
        "",
    ]

    if not top:
        lines.append("ℹ️ No points yet for this period.")
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

    # -------------------------------------------------
    # User rank section
    # -------------------------------------------------

    lines.append("")

    if my_rank_from_top is not None:
        lines.append(
            f"📍 <b>Your rank:</b> {my_rank_from_top} / <b>{my_points_from_top}</b> pts"
        )
    else:
        if my_rank is None:
            lines.append("📍 <b>Your rank:</b> unranked (0 pts)")
        else:
            lines.append(
                f"📍 <b>Your rank:</b> {int(my_rank)} / <b>{int(my_points or 0)}</b> pts"
            )

    await reply_safe(message, "\n".join(lines), parse_mode="HTML")
