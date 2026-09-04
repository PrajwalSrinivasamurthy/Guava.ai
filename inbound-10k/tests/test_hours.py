"""Direct coverage of utils.is_open()'s real weekday/time-window branch.

Every other test in this suite runs under the `_hours_open` autouse fixture, which forces
FORCE_HOURS to "open" or "after" — so the actual production fallthrough (settings.PRACTICE_HOURS
lookup + string time comparison) never ran anywhere else. These tests clear FORCE_HOURS and
drive is_open() with an injected datetime instead of the real clock.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import utils


def test_is_open_true_inside_a_weekday_window(app):
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 10, 0, tzinfo=tz)  # Tuesday, mid-morning

    assert utils.is_open(now) is True


def test_is_open_true_inside_the_afternoon_window(app):
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 14, 0, tzinfo=tz)  # Tuesday, mid-afternoon

    assert utils.is_open(now) is True


def test_is_open_false_during_the_lunch_closure(app):
    """Practice hours are 8-12 and 13-17 — the gap between is closed."""
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 12, 0, tzinfo=tz)  # Tuesday, noon

    assert utils.is_open(now) is False


def test_is_open_false_just_before_the_open_boundary(app):
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 7, 59, tzinfo=tz)

    assert utils.is_open(now) is False


def test_is_open_true_at_the_open_boundary(app):
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 8, 0, tzinfo=tz)

    assert utils.is_open(now) is True


def test_is_open_false_at_the_close_boundary(app):
    """The window is [open, close) — closing time itself is already closed."""
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 8, 17, 0, tzinfo=tz)

    assert utils.is_open(now) is False


def test_is_open_false_on_a_weekend(app):
    app.settings.FORCE_HOURS = ""
    tz = ZoneInfo(app.settings.PRACTICE_TZ)
    now = datetime(2026, 9, 12, 12, 0, tzinfo=tz)  # Saturday

    assert utils.is_open(now) is False
