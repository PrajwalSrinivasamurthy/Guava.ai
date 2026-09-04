"""
Tier 2 — `agent.test()`: real Dialog Engine, scripted caller turns.

10K's routing is a plain dict lookup (destinations.py) — already proven offline in
test_destinations.py. What's left for the engine to prove: does a real spoken choice
actually classify into the right next_step, and does the after-hours enrollment funnel
(10 fields, always a hangup) actually complete over the wire without ever transferring.

Assertions are deterministic spies, never `executed_actions`.

The "route" task's completion_criteria is just "Complete once next_step is known" —
no confirmation turn before transferring. Traced against the source playbook: none
of Ava/live-agent/voicemail are gated behind an "anything else?" prompt there either —
that prompt exists only in the enrollment hang-up flow ("Any Thing Else", reached from
"ThankYouForCalling"), and even the "live agent" page's "Do you mind holding?" is asked
on an `is_exit_page: true` page, so the transfer fires regardless of the answer.

"Never transfers" (the enrollment funnel) is asserted by spying `guava.Call.transfer`
directly, NOT `agent_testing.transfers_of` on a captured live Call. `_command_queue` is
a real `queue.Queue` that a background thread drains to send commands over the
websocket in real time — by the time a live session ends it's already been consumed,
and iterating the raw Queue raises `TypeError: 'Queue' object is not iterable`.
`transfers_of`/`commands_of` only work on `MockCall` or a bare `Call` from a *direct*
handler call (see their docstrings) — never on a live session's Call. `capture_call` is
still used, just for `get_field` reads.

    RUN_LIVE=1 uv run --env-file .env pytest tests/test_scripted.py -v
"""

import guava
from agent_testing import capture_call, spy
from conftest import requires_live

pytestmark = requires_live


# ── Open-hours routing ──────────────────────────────────────────────────────────

def test_open_hours_virtual_assistant_request_reaches_ava(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'd like to be connected to the virtual assistant, please.")
        session.wait_for_end()

    r = record(session, "open_hours_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.ELEVENLABS_NUMBER


def test_open_hours_talk_to_a_live_agent_reaches_the_live_queue(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("Can I speak to a live agent, please?")
        session.wait_for_end()

    r = record(session, "open_hours_talk_to_live_agent")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.LIVE_NUMBER


# ── After-hours non-enrollment routing ──────────────────────────────────────────

def test_after_hours_general_information_reaches_ava(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "after"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I just have a general question, not looking to enroll.")
        session.wait_for_end()

    r = record(session, "after_hours_general_information")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.ELEVENLABS_NUMBER


def test_after_hours_leave_a_voicemail_reaches_the_live_queue(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "after"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'd like to leave a voicemail.")
        session.wait_for_end()

    r = record(session, "after_hours_leave_a_voicemail")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.LIVE_NUMBER


# ── After-hours enrollment funnel ────────────────────────────────────────────────

def test_after_hours_enrollment_completes_and_hangs_up_never_transfers(app, record, monkeypatch):
    """The lead-capture funnel converges on a hangup regardless of answers (see
    __main__.py's _start_enrollment docstring) — this proves that holds over the wire,
    not just as a MockCall command-queue check."""
    app.settings.FORCE_HOURS = "after"
    captured = capture_call(monkeypatch, app.agent)
    transfers = spy(monkeypatch, guava.Call, "transfer")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'd like to enroll in the program.")
        session.wait_for_turn()
        session.say("I found out about it online.")
        session.wait_for_turn()
        session.say("Yes, I'm interested.")
        session.wait_for_turn()
        session.say("My first name is Jordan.")
        session.wait_for_turn()
        session.say("Last name Ellis.")
        session.wait_for_turn()
        session.say("You can reach me at 214-555-0136.")
        session.wait_for_turn()
        session.say("jordan.ellis@example.com.")
        session.wait_for_turn()
        session.say("I'd prefer email.")
        session.wait_for_turn()
        session.say("I'm hoping to start next semester.")
        session.wait_for_turn()
        session.say("I have 45 credits.")
        session.wait_for_turn()
        session.say("I live in Fort Worth.")
        session.wait_for_turn()
        session.say("Yes, I can travel to Irving for the in-person sessions.")
        session.wait_for_end()

    r = record(session, "after_hours_enrollment_completes")
    assert r["termination_reason"] != "bot-failure"
    assert captured, "on_call_start never fired — no Call was captured"
    assert transfers == [], "the enrollment funnel must never transfer"
    assert captured[0].get_field("first_name") == "Jordan"
    assert captured[0].get_field("last_name") == "Ellis"
    assert captured[0].get_field("college_credits") == 45


def test_declining_enrollment_still_completes_without_a_transfer(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "after"
    captured = capture_call(monkeypatch, app.agent)
    transfers = spy(monkeypatch, guava.Call, "transfer")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'd like to enroll in the program.")
        session.wait_for_turn()
        session.say("Actually, no, I'm not interested right now.")
        session.wait_for_end()

    r = record(session, "declining_enrollment")
    assert r["termination_reason"] != "bot-failure"
    assert transfers == []
    assert captured[0].get_field("enrollment_interested") == "No"
