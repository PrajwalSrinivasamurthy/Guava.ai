"""Pure helpers extracted from __main__.py so the call flow reads without noise."""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import settings

_TZ = ZoneInfo(settings.PRACTICE_TZ)


def is_open(now: Optional[datetime] = None) -> bool:
    """Business-hours gate, computed at runtime. HOURS=open|after (settings.FORCE_HOURS)
    overrides for testing only — production always falls through to the real clock."""
    if settings.FORCE_HOURS == "open":
        return True
    if settings.FORCE_HOURS in ("after", "closed"):
        return False
    now = now or datetime.now(_TZ)
    windows = settings.PRACTICE_HOURS.get(now.weekday())
    if not windows:
        return False
    clock = now.strftime("%H:%M")
    return any(start <= clock < end for start, end in windows)


def holiday_name(now: Optional[datetime] = None) -> Optional[str]:
    """Returns today's holiday name if configured, else None. Only meaningful when
    is_open() is False. FORCE_HOLIDAY_NAME env override for testing only."""
    if settings.FORCE_HOLIDAY_NAME:
        return settings.FORCE_HOLIDAY_NAME
    now = now or datetime.now(_TZ)
    return settings.HOLIDAYS.get(now.date().isoformat())
