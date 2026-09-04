import os

ORGANIZATION_NAME = "Texas Tech K-12"
AGENT_NAME = "Grace"
AGENT_VOICE = "grace"
AGENT_LANGUAGE = "english"
AGENT_SECONDARY_LANGUAGES = ["spanish"]

# Destination numbers, from a fresh legacy-platform snapshot (2026-09-02).
LIVE_NUMBER = os.environ.get("LIVE_NUMBER", "+18067427101")
ELEVENLABS_NUMBER = os.environ.get("ELEVENLABS_NUMBER", "+18884178511")

# Practice-hours gate. PLACEHOLDER window (Mon-Fri 8am-noon, 1pm-5pm Central) — confirm Texas Tech
# K-12's actual business hours before going live. Real clock decides in production; see
# utils.is_open(). Days not present in this dict (Sat/Sun here) are treated as closed.
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

# SMS sending for the after-hours "receive a text message" option. False disables real sends
# (tests always force this false via the _no_real_sms fixture regardless of this value).
SMS_ENABLED = os.environ.get("SMS_ENABLED", "true").lower() != "false"

# Confirmed with Texas Tech K-12 (2026-09-03): the information-portal link (current
# students) and the RFI contact-form link (prospective/non-students). Empty disables the
# text-message option's link (sms.py degrades to a spoken apology instead of texting a
# broken/placeholder link).
K12_SERVICENOW_PORTAL_URL = os.environ.get("K12_SERVICENOW_PORTAL_URL", "https://www.support.k12.ttu.edu/k12")
K12_RFI_FORM_URL = os.environ.get(
    "K12_RFI_FORM_URL",
    "https://us7.list-manage.com/contact-form?u=243e95220468b6d24bb860f6c&form_id=8a94a01396b573f1f1490d940c1351cc",
)

# FAQ content for on_question / DocumentQA, loaded via config_sheet.py.
# Empty by default — no committed seed exists yet since no content existed prior to a
# real Sheet. Set this once one exists.
FAQ_SPREADSHEET_ID = os.environ.get("FAQ_SPREADSHEET_ID", "")

# This program's tab within that spreadsheet. Other programs (Online, Grad, 10K) use
# their own tabs in the same spreadsheet, not a shared tab filtered by a program column.
# Legacy Grace's K12 bots used two distinct KBs for day vs. after-hours ("K12 (PRD)" /
# "K12 AH (PRD)") — this rebuild deliberately uses one tab for both, like the other
# 3 programs.
FAQ_SHEET_TAB = os.environ.get("FAQ_SHEET_TAB", "K12 FAQs")

PRONUNCIATIONS: dict[str, str] = {
    "live agents": "lyve agents",
    "live agent": "lyve agent",
    "live in": "live in",
}
