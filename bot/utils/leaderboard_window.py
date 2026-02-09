from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class LeaderboardWindow:
    kind: str  # "campaign" | "weekly"
    start: date
    end: date


# 🔧 CONFIG (minimum effort)
CAMPAIGN_START = date(2026, 2, 5)
CAMPAIGN_END = date(2026, 2, 12)  # inclusive, snapshot + announce


def sunday_week_start(day: date) -> date:
    # Sunday = 6
    days_since_sunday = (day.weekday() + 1) % 7
    return day - timedelta(days=days_since_sunday)


def resolve_leaderboard_window(today: date) -> LeaderboardWindow:
    """
    Priority:
    1. Active campaign (display only)
    2. Default weekly (Sunday → Sunday)
    """

    # 🟢 Campaign override
    if CAMPAIGN_START <= today <= CAMPAIGN_END:
        return LeaderboardWindow(
            kind="campaign",
            start=CAMPAIGN_START,
            end=CAMPAIGN_END,
        )

    # 🔵 Default weekly
    ws = sunday_week_start(today)
    return LeaderboardWindow(
        kind="weekly",
        start=ws,
        end=ws + timedelta(days=6),
    )
