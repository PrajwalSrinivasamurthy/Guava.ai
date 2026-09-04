"""
Tier 2 — `agent.test()`: real Dialog Engine, scripted caller turns.

Online is the front-door triage agent — the richest routing surface of the 4 (a 3-key
program/online_service/continue_with table, already proven offline in
test_destinations.py). What's left for the engine to prove: does a real caller's own
words about their situation actually classify into the right `program` /
`online_service` fields, including the "Not sure" fallback and the guard against ever
reaching the confirmed-dead self-paced-rep number.

Assertions are deterministic spies, never `executed_actions`.

No confirmation turn before transferring: none of the program/Ava/live-queue
destinations are gated behind an "anything else?" prompt — every choice links straight
to its exit page, so the last caller turn ends the flow.

    RUN_LIVE=1 uv run --env-file .env pytest tests/test_scripted.py -v
"""

import pytest
from agent_testing import spy
from conftest import LIVE_RUNS, requires_live

pytestmark = requires_live

_runs = pytest.mark.parametrize("run", range(LIVE_RUNS))


def test_k12_program_with_live_team_member_choice_routes_to_the_k12_live_queue(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the K-12 program.")
        session.wait_for_turn()
        session.say("I'd like to talk to a live team member.")
        session.wait_for_end()

    r = record(session, "k12_program_live_team_member")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.K12_NUMBER


def test_10k_program_with_virtual_assistant_choice_routes_to_10k_elevenlabs(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the 10K Degree Completion program.")
        session.wait_for_turn()
        session.say("Connect me with the virtual assistant.")
        session.wait_for_end()

    r = record(session, "10k_program_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.TENK_ELEVENLABS_NUMBER


def test_online_flexible_learning_service_routes_to_the_flexible_learning_line(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("Flexible Learning.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "online_flexible_learning")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.FLEXIBLE_LEARNING_NUMBER


def test_graduate_program_with_virtual_assistant_choice_routes_to_grad_elevenlabs(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the Graduate program.")
        session.wait_for_turn()
        session.say("Connect me to the virtual assistant.")
        session.wait_for_end()

    r = record(session, "graduate_program_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.GRAD_ELEVENLABS_NUMBER


def test_graduate_program_with_live_team_member_choice_routes_to_the_grad_live_queue(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the Graduate program.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "graduate_program_live_team_member")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.GRAD_NUMBER


def test_k12_program_with_virtual_assistant_choice_routes_to_k12_elevenlabs(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the K-12 program.")
        session.wait_for_turn()
        session.say("Connect me to the virtual assistant.")
        session.wait_for_end()

    r = record(session, "k12_program_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.K12_ELEVENLABS_NUMBER


def test_10k_program_with_live_team_member_choice_routes_to_the_10k_live_queue(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about the 10K Degree Completion program.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "10k_program_live_team_member")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.TENK_NUMBER


def test_online_program_with_virtual_assistant_choice_routes_to_online_elevenlabs(
        app, record, monkeypatch):
    """Online's own virtual-assistant destination — reached regardless of
    online_service, since destinations.resolve() sets key_service=None whenever
    wants_ai is True (an Ava request never needs to know which Online sub-service the
    caller meant)."""
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("Connect me to the virtual assistant.")
        session.wait_for_end()

    r = record(session, "online_program_virtual_assistant")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.ONLINE_ELEVENLABS_NUMBER


def test_online_degree_completion_service_routes_to_the_signature_plus_rep_line(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("Degree completion, the Online Plus program.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "online_degree_completion")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.SIGNATURE_PLUS_REP_NUMBER


def test_online_microcredentials_service_routes_to_the_flexible_learning_line(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("Microcredentials.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "online_microcredentials")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.FLEXIBLE_LEARNING_NUMBER


def test_online_career_certificates_service_routes_to_the_flexible_learning_line(
        app, record, monkeypatch):
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("Career Certificates.")
        session.wait_for_turn()
        session.say("I'd like a live team member.")
        session.wait_for_end()

    r = record(session, "online_career_certificates")
    assert r["termination_reason"] != "bot-failure"
    assert resolved and resolved[-1]["result"].number == app.settings.FLEXIBLE_LEARNING_NUMBER


def test_a_caller_who_is_not_sure_stays_with_the_bot_during_open_hours(app, record):
    """No destination exists for "unsure which program" during business hours — the
    agent keeps helping instead of transferring anywhere.

    completion_criteria explicitly tells the model not to complete the route task while
    the caller stays unsure, so the correct path never re-opens it via _build_route_task
    — it just keeps answering inside the same task. The closing line below ends the call
    on a real caller action instead of racing the agent's follow-up question into an
    idle-timeout hangup."""
    app.settings.FORCE_HOURS = "open"

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm honestly not sure which program I need.")
        session.wait_for_turn()
        session.say("Can you tell me a bit about the online options?")
        session.wait_for_turn()
        session.say("No, none of those quite fit — that's all I needed, thanks, bye.")
        session.wait_for_end()

    r = record(session, "not_sure_stays_with_bot")
    assert r["termination_reason"] != "bot-failure"
    assert r["termination_reason"] != "bot-transfer"


def test_a_caller_who_is_not_sure_falls_back_to_the_higher_ed_default_after_hours(app, record):
    """Same "unsure which program" case, but after hours: no live team to keep helping
    with, so it falls back to the Higher Ed Default voicemail instead of looping."""
    app.settings.FORCE_HOURS = "after"

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm honestly not sure which program I need.")
        session.wait_for_end()

    r = record(session, "not_sure_falls_back_after_hours")
    assert r["termination_reason"] != "bot-failure"
    assert r["termination_reason"] == "bot-transfer"


@_runs
def test_self_paced_phrasing_never_resolves_to_the_dead_number(app, record, monkeypatch, run):
    """A safety guard, not a preference: this number is confirmed dead in the legacy
    graph, so no phrasing of the caller's request should ever reach it.
    Repeated over LIVE_RUNS because this checks classifier stability on one fixed but
    ambiguous line, not a rate over varied speech (no agent.roleplay() here)."""
    app.settings.FORCE_HOURS = "open"
    resolved = spy(monkeypatch, app.destinations, "resolve")

    with app.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm calling about Texas Tech Online.")
        session.wait_for_turn()
        session.say("The self-paced option.")
        session.wait_for_turn()
        session.say("I'd like a live person.")
        session.wait_for_end()

    r = record(session, f"self_paced_phrasing_{run}")
    assert r["termination_reason"] != "bot-failure"
    numbers = [c["result"].number for c in resolved]
    assert app.destinations.UNREACHABLE_SELF_PACED_REP_NUMBER not in numbers
