import os

ORGANIZATION_NAME = "Texas Tech Graduate School"
AGENT_NAME = "Grace"
AGENT_VOICE = "grace"
AGENT_LANGUAGE = "english"
AGENT_SECONDARY_LANGUAGES = ["spanish"]

# Destination numbers, confirmed 2026-09-02.
LIVE_NUMBER = os.environ.get("LIVE_NUMBER", "+18067426441")
ELEVENLABS_NUMBER = os.environ.get("ELEVENLABS_NUMBER", "+18883323870")

# Practice-hours gate. PLACEHOLDER window (Mon-Fri 8am-noon, 1pm-5pm Central) — confirm Texas Tech
# Graduate School's actual business hours before going live. Real clock decides in
# production; see utils.is_open(). Days not present in this dict (Sat/Sun here) are
# treated as closed.
PRACTICE_TZ = os.environ.get("PRACTICE_TZ", "America/Chicago")
PRACTICE_HOURS = {
    0: [("08:00", "12:00"), ("13:00", "17:00")],  # Monday
    1: [("08:00", "12:00"), ("13:00", "17:00")],
    2: [("08:00", "12:00"), ("13:00", "17:00")],
    3: [("08:00", "12:00"), ("13:00", "17:00")],
    4: [("08:00", "12:00"), ("13:00", "17:00")],
}

# Test-only override, NOT the production mechanism — utils.is_open() only consults this
# when set. Forces a branch for live-call testing / the automated test suite.
FORCE_HOURS = os.environ.get("HOURS", "")

# Legacy Grace's holiday gate ("Time of Day (Holidays/Weekend)" connector) fed in real holiday
# dates; this export doesn't carry the actual calendar. PLACEHOLDER — empty means the holiday
# branch is never taken (falls through to the plain after-hours message). Confirm Texas Tech's
# actual holiday calendar (dates + spoken names) before going live.
HOLIDAYS: dict[str, str] = {}  # {"2026-11-26": "Thanksgiving", ...}

# Test-only override, NOT the production mechanism — utils.holiday_name() only consults this
# when set (and only matters when the real clock/FORCE_HOURS says closed).
FORCE_HOLIDAY_NAME = os.environ.get("FORCE_HOLIDAY_NAME", "")

SMS_ENABLED = os.environ.get("SMS_ENABLED", "true").lower() != "false"

# Still open: the legacy playbook this was rebuilt from also had a separate RFI-form
# connector alongside the ServiceNow one (a student-status question branching between
# the two) — this rebuild only implements the single ServiceNow-style path below;
# confirm whether Grad needs the RFI branch too. Empty disables the text-message
# option's link (degrades to a spoken apology).
GRAD_SERVICENOW_PORTAL_URL = os.environ.get("GRAD_SERVICENOW_PORTAL_URL", "https://askit.ttu.edu")

# FAQ content for on_question / DocumentQA, loaded via config_sheet.py.
# Empty by default — no committed seed exists yet since no content existed prior to a
# real Sheet. Set this once one exists.
FAQ_SPREADSHEET_ID = os.environ.get("FAQ_SPREADSHEET_ID", "")

# This program's tab within that spreadsheet. Other programs (Online, K12, 10K) use
# their own tabs in the same spreadsheet, not a shared tab filtered by a program column.
FAQ_SHEET_TAB = os.environ.get("FAQ_SHEET_TAB", "Grad FAQs")

PRONUNCIATIONS: dict[str, str] = {
    "live agents": "lyve agents",
    "live agent": "lyve agent",
    "Live agents": "Lyve agents",
    "Live agent": "Lyve agent",
    "live in": "live in",
}
