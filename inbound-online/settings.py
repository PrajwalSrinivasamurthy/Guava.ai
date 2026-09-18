import os

ORGANIZATION_NAME = "Texas Tech Online"
AGENT_NAME = "Grace"
AGENT_VOICE = "grace"
AGENT_LANGUAGE = "english"
AGENT_SECONDARY_LANGUAGES = ["spanish"]

# Destination table — from Grace implementation
SIGNATURE_PLUS_REP_NUMBER = os.environ.get("SIGNATURE_PLUS_REP_NUMBER", "+18067422810")
HIGHER_ED_DEFAULT_NUMBER = os.environ.get("HIGHER_ED_DEFAULT_NUMBER", "+18067427227")
FLEXIBLE_LEARNING_NUMBER = os.environ.get("FLEXIBLE_LEARNING_NUMBER", "+18067423714")
GRAD_NUMBER = os.environ.get("GRAD_NUMBER", "+18067426441")
K12_NUMBER = os.environ.get("K12_NUMBER", "+18067427101")
TENK_NUMBER = os.environ.get("TENK_NUMBER", "+18067420526")

ONLINE_ELEVENLABS_NUMBER = os.environ.get("ONLINE_ELEVENLABS_NUMBER", "+18882817949")
K12_ELEVENLABS_NUMBER = os.environ.get("K12_ELEVENLABS_NUMBER", "+18884178511")
GRAD_ELEVENLABS_NUMBER = os.environ.get("GRAD_ELEVENLABS_NUMBER", "+18883323870")
TENK_ELEVENLABS_NUMBER = os.environ.get("TENK_ELEVENLABS_NUMBER", "+18889707775")

# Practice-hours gate. Confirmed with Texas Tech (2026-09-17): the support center staggers
# staff lunches, so it's continuously open 8am-5pm Central with no midday closure. Days not
# present in this dict (Sat/Sun here) are treated as closed.
PRACTICE_TZ = os.environ.get("PRACTICE_TZ", "America/Chicago")
PRACTICE_HOURS = {
    0: [("08:00", "17:00")],  # Monday
    1: [("08:00", "17:00")],
    2: [("08:00", "17:00")],
    3: [("08:00", "17:00")],
    4: [("08:00", "17:00")],
}

# Test-only override, NOT the production mechanism — utils.is_open() only consults this
# when set. Forces a branch for live-call testing / the automated test suite.
FORCE_HOURS = os.environ.get("HOURS", "")

# TTU's official holiday schedule (https://www.depts.ttu.edu/hr/empbenefits/holidayschedule.php),
# pulled 2026-09-17. 2027 only has the dates TTU HR has published so far.
HOLIDAYS: dict[str, str] = {
    "2026-01-01": "New Year's Day",
    "2026-01-02": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-03-20": "Spring Break",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Emancipation Day",
    "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving",
    "2026-11-27": "Thanksgiving",
    "2026-12-23": "Winter Break",
    "2026-12-24": "Winter Break",
    "2026-12-25": "Winter Break",
    "2026-12-28": "Winter Break",
    "2026-12-29": "Winter Break",
    "2026-12-30": "Winter Break",
    "2026-12-31": "Winter Break",
    "2027-01-01": "New Year's Day",
    "2027-01-18": "Martin Luther King Jr. Day",
    "2027-03-19": "Spring Break",
    "2027-05-31": "Memorial Day",
}

# Test-only override, NOT the production mechanism — utils.holiday_name() only consults this
# when set (and only matters when the real clock/FORCE_HOURS says closed).
FORCE_HOLIDAY_NAME = os.environ.get("FORCE_HOLIDAY_NAME", "")

# FAQ content for on_question / DocumentQA, loaded via config_sheet.py.
# Empty by default — falls back to the committed config_cache.json seed (generated once
# from texas_tech_online_kb.md's initial content). Set this once a real Sheet exists.
FAQ_SPREADSHEET_ID = os.environ.get("FAQ_SPREADSHEET_ID", "")

# This program's tab within that spreadsheet. Other programs (K12, 10K) use their own
# tabs in the same spreadsheet, not a shared tab filtered by a program column.
FAQ_SHEET_TAB = os.environ.get("FAQ_SHEET_TAB", "Online FAQs")

PRONUNCIATIONS: dict[str, str] = {
    "live in": "live in",
}

# How often live_config.start_poller() re-pulls FAQs + phone numbers from the live
# sheet. Set to a large value (or wire up a way to skip start_poller()) to effectively
# disable polling without a code change.
CONFIG_POLL_SECONDS = int(os.environ.get("CONFIG_POLL_SECONDS", "60"))
