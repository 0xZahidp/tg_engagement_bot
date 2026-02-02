from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class TimeProvider:
    timezone: str = "UTC"

    def today(self) -> date:
        tz = ZoneInfo(self.timezone)
        return datetime.now(tz=tz).date()
