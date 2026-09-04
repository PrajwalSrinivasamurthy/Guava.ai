import os

ORGANIZATION_NAME = "Texas Tech 10K Degree Completion Program"
AGENT_NAME = "Grace"

# Destination numbers. The call-flow export only
# wires two outlet nodes for this program (LIVE_NUMBER, ELEVENLABS_NUMBER); the
# playbook's "End - Transfer to Live Agent" outcome has no dedicated outlet node in the
# export — mapped here to LIVE_NUMBER, the only live destination this program has.
LIVE_NUMBER = os.environ.get("LIVE_NUMBER", "+18067420526")
ELEVENLABS_NUMBER = os.environ.get("ELEVENLABS_NUMBER", "+18889707775")

# Practice-hours gate. PLACEHOLDER window (Mon-Fri 8am-noon, 1pm-5pm Central) — confirm Texas Tech
# 10K's actual business hours before going live. Real clock decides in production; see
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

# FAQ content for on_question / DocumentQA, loaded via config_sheet.py.
# Empty by default — no committed seed exists yet since no content existed prior to a
# real Sheet. Set this once one exists.
FAQ_SPREADSHEET_ID = os.environ.get("FAQ_SPREADSHEET_ID", "")

# This program's tab within that spreadsheet. Other programs (Online, Grad, K12) use
# their own tabs in the same spreadsheet, not a shared tab filtered by a program column.
FAQ_SHEET_TAB = os.environ.get("FAQ_SHEET_TAB", "10K FAQs")
