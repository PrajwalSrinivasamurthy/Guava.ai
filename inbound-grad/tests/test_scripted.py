"""
Tier 2 — `agent.test()`: real Dialog Engine, scripted caller turns.

Grad's routing is a plain dict lookup (destinations.py) — already proven offline in
test_destinations.py. What's left for the engine to prove: does a real spoken choice
actually classify into the right continue_with, and does the after-hours "text me the
link" choice actually send the SMS and hang up without ever transferring, over the wire.

Assertions are deterministic spies, never `executed_actions`. The SMS chokepoint is
patched directly on `app.sms.send_link` — the autouse `_no_real_sms` fixture only
guards `guava.Client`, which this patch bypasses entirely.

The "route" task's completion_criteria is just "Complete once continue_with is known" —
no confirmation turn before transferring or sending the text. None of
Ava/live-queue/voicemail/text-message are gated behind an "anything else?" prompt —
every choice links straight to its exit page, so a single turn is enough.

"Never transfers" is asserted by spying `guava.Call.transfer` directly, NOT
`agent_testing.transfers_of` on a captured live Call. `_command_queue` is a real
`queue.Queue` that a background thread drains to send commands over the websocket in
real time — by the time a live session ends it's already been consumed, and iterating
the raw Queue raises `TypeError: 'Queue' object is not iterable`. `transfers_of`/
`commands_of` only work on `MockCall` or a bare `Call` from a *direct* handler call
(see their docstrings) — never on a live session's Call.

    RUN_LIVE=1 uv run --env-file .env pytest tests/test_scripted.py -v
"""

import guava
from agent_testing import spy
from conftest import requires_live

pytestmark = requires_live


def test_after_hours_text_message_choice_sends_the_portal_link_and_never_transfers(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "after"
    sent = []
    monkeypatch.setattr(
        app.sms, "send_link",
        lambda to, url, prefix: (sent.append((to, url, prefix)), True)[1])
    transfers = spy(monkeypatch, guava.Call, "transfer")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("Can you just text me the link to submit a ticket?")
        session.wait_for_end()

    r = record(session, "after_hours_text_message")
    assert r["termination_reason"] != "bot-failure"
    assert len(sent) == 1, f"expected exactly one text send, got {sent}"
    assert sent[0][1] == app.settings.GRAD_SERVICENOW_PORTAL_URL
    assert transfers == []


def test_open_hours_live_team_member_request_reaches_the_live_queue(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I want to talk to a live team member.")
        session.wait_for_end()

    r = record(session, "open_hours_live_team_member")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.LIVE_NUMBER


def test_after_hours_voicemail_request_reaches_the_live_queue(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "after"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'd like to leave a voicemail for the team.")
        session.wait_for_end()

    r = record(session, "after_hours_voicemail")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.LIVE_NUMBER


def test_open_hours_virtual_assistant_request_reaches_ava(app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("Connect me to the virtual assistant.")
        session.wait_for_end()

    r = record(session, "open_hours_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.ELEVENLABS_NUMBER


def test_after_hours_questions_request_reaches_ava(app, record, monkeypatch):
    """After hours offers the same 'Be connected to our virtual assistant' choice as
    daytime (see __main__.py's continue_field), just alongside voicemail/text-message
    instead of the live queue. An unspecific line like 'I just have a question' isn't
    enough on its own — the agent correctly asks what the question is / which of the
    3 AH options they want instead of guessing, so a scripted single-turn session times
    out. Ask for the virtual assistant directly, same as the daytime test above."""
    app.settings.FORCE_HOURS = "after"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("Connect me to the virtual assistant.")
        session.wait_for_end()

    r = record(session, "after_hours_questions")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.ELEVENLABS_NUMBER
