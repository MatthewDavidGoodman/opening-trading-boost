from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import TimeWindow

_WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def is_window_open(window: TimeWindow, when_utc: datetime | None = None) -> bool:
    when = when_utc or now_utc()
    if when.tzinfo is None:
        raise ValueError("when_utc must be timezone-aware")
    local = when.astimezone(ZoneInfo(window.timezone))
    day_name = _WEEKDAY_NAMES[local.weekday()]
    if day_name not in window.days:
        return False
    return window.start <= local.time() <= window.end
