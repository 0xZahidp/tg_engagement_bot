# bot/utils/dates.py
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def week_start_monday(d: date) -> date:
    # Monday = 0 ... Sunday = 6
    return d - timedelta(days=d.weekday())
