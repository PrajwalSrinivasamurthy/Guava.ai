import os

ORGANIZATION_NAME = "Texas Tech 10K Degree Completion Program"
AGENT_NAME = "Grace"
AGENT_VOICE = "grace"
AGENT_LANGUAGE = "english"
AGENT_SECONDARY_LANGUAGES = ["spanish"]

# Destination numbers. The call-flow export only
# wires two outlet nodes for this program (LIVE_NUMBER, ELEVENLABS_NUMBER); the
# playbook's "End - Transfer to Live Agent" outcome has no dedicated outlet node in the
# export — mapped here to LIVE_NUMBER, the only live destination this program has.
LIVE_NUMBER = os.environ.get("LIVE_NUMBER", "+18067420526")
ELEVENLABS_NUMBER = os.environ.get("ELEVENLABS_NUMBER", "+18889707775")

# Practice-hours gate. Confirmed with Texas Tech (2026-09-17): the support center staggers
# staff lunches, so it's continuously open 8am-5pm Central with no midday closure. Real
# clock decides in production; see utils.is_open(). Days not present in this dict
# (Sat/Sun here) and dates in HOLIDAYS below are treated as closed.
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

# TTU's official holiday schedule (https://www.depts.ttu.edu/hr/empbenefits/holidayschedule.php).
# 2027 only has the dates TTU HR has published so far.
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

# Legacy "TTU Online -> Power Automate (10K)" connector — pushes captured enrollment leads
# to this Power Automate flow's HTTP trigger, which then writes them to SharePoint. Carried
# over as-is from the legacy IVR platform's connector script (2026-09-17); the `sig` query
# param is itself this trigger's auth. TENK_POWER_AUTOMATE_API_KEY is an optional extra
# x-api-key header some flows also check — unset by default (the legacy script always sent
# an empty one), set in .env if the flow requires it.
TENK_POWER_AUTOMATE_URL = os.environ.get(
    "TENK_POWER_AUTOMATE_URL",
    "https://default178a51bf8b2049ffb65556245d5c17.3c.environment.api.powerplatform.com:443/"
    "powerautomate/automations/direct/cu/00/workflows/3c61edffc6ae4ed5bc01ece50948f010/triggers/"
    "manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0"
    "&sig=Yk_pkbuv7AoCtuT9fJU-SJYxPgrqibHQ9NtHbs6AVhs",
)
TENK_POWER_AUTOMATE_API_KEY = os.environ.get("TENK_POWER_AUTOMATE_API_KEY", "")

# FAQ content for on_question / DocumentQA, loaded via config_sheet.py.
# Empty by default — no committed seed exists yet since no content existed prior to a
# real Sheet. Set this once one exists.
FAQ_SPREADSHEET_ID = os.environ.get("FAQ_SPREADSHEET_ID", "")

# This program's tab within that spreadsheet. Other programs (Online, Grad, K12) use
# their own tabs in the same spreadsheet, not a shared tab filtered by a program column.
FAQ_SHEET_TAB = os.environ.get("FAQ_SHEET_TAB", "10K FAQs")

PRONUNCIATIONS: dict[str, str] = {
    "live in": "live in",
}

# How often live_config.start_poller() re-pulls FAQs + phone numbers from the live
# sheet. Set to a large value (or wire up a way to skip start_poller()) to effectively
# disable polling without a code change.
CONFIG_POLL_SECONDS = int(os.environ.get("CONFIG_POLL_SECONDS", "60"))
