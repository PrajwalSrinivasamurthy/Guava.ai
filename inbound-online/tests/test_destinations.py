"""One test per named Grace destination, plus the guardrails around it.

See destinations.py — the parametrization below iterates destinations.ROUTES directly
so this list can never drift from the routing table itself.
"""

import pytest

import destinations


def _set_answers(call, program, online_service, continue_with):
    call.set_field("program", program)
    if online_service is not None:
        call.set_field("online_service", online_service)
    call.set_field("continue_with", continue_with)


def _transfers(call):
    return [c for c in call._command_queue if type(c).__name__ == "TransferCommand"]


def _transfer_numbers(call):
    return [c.to_number for c in _transfers(call)]


_TRANSFER_DIRECTIVE_CUES = ("then transfer", "right away", "one moment", "just a moment", "moment, please", "hold for")


def _ends_with_transfer_directive(message):
    """A custom transfer message must end on an immediacy directive, or the Dialog
    Engine may offer to transfer instead of doing it and stall on silence waiting
    for a confirmation that was never asked for."""
    tail = message.strip().rstrip(".").lower()
    return any(tail.endswith(cue) for cue in _TRANSFER_DIRECTIVE_CUES)


@pytest.mark.parametrize(
    "program,online_service,wants_ai,expected",
    [(*key, dest) for key, dest in destinations.ROUTES.items()],
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values()],
)
def test_route_reaches_its_grace_destination(app, call, program, online_service, wants_ai, expected):
    continue_with = "Be connected to our virtual assistant" if wants_ai else "Be transferred to a live team member"
    _set_answers(call, program, online_service, continue_with)

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == expected.number


@pytest.mark.parametrize(
    "program,online_service,wants_ai,expected",
    [(*key, dest) for key, dest in destinations.ROUTES.items()],
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values()],
)
def test_transfer_message_carries_an_immediacy_directive(app, call, program, online_service, wants_ai, expected):
    continue_with = "Be connected to our virtual assistant" if wants_ai else "Be transferred to a live team member"
    _set_answers(call, program, online_service, continue_with)

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


def test_unnamed_program_falls_back_to_higher_ed_default_after_hours(app, call):
    """No destination exists for "unsure which program" during business hours — the
    caller stays with the bot instead (see the loop-back test below). After hours,
    with no live team to reach, an unresolved program always falls back to voicemail —
    continue_with isn't asked at all in this case, so it's irrelevant to the outcome."""
    app.settings.FORCE_HOURS = "after"
    call.set_field("program", "Not sure")

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == destinations.FALLBACK.number


def test_fallback_transfer_message_carries_an_immediacy_directive(app, call):
    app.settings.FORCE_HOURS = "after"
    call.set_field("program", "Not sure")

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


def test_unsure_program_stays_with_the_bot_during_open_hours(app, call):
    """No destination exists for "unsure which program" during business hours — keep
    the caller talking to the bot instead of transferring anywhere. continue_with isn't
    asked in this case at all, so the outcome doesn't depend on it being set."""
    call.set_field("program", "Not sure")

    app.on_route_complete(call)

    assert _transfers(call) == []
    set_task_calls = [c for c in call._command_queue if type(c).__name__ == "SetTaskCommand"]
    assert len(set_task_calls) == 2, "expected on_call_start's task plus a re-opened one"


@pytest.mark.parametrize(
    "program,online_service",
    [(key[0], key[1]) for key in destinations.ROUTES if key[2] is False],
)
def test_after_hours_voicemail_reaches_higher_ed_default(program, online_service):
    """SCENARIOS.md: no live-queue/rep-line number is reachable after hours in the
    legacy AH playbook — only Higher Ed Default and the 4 ElevenLabs numbers. "Leave a
    voicemail" (only offered when closed) must not fall through to a program's live queue."""
    dest = destinations.resolve(program, online_service, "Leave a voicemail")
    assert dest == destinations.FALLBACK


def test_self_paced_rep_stays_unreachable():
    """This legacy number has no reachable path — guard against ever accidentally
    re-wiring it."""
    live_numbers = {dest.number for dest in destinations.ROUTES.values()} | {destinations.FALLBACK.number}
    assert destinations.UNREACHABLE_SELF_PACED_REP_NUMBER not in live_numbers


def test_escalate_transfers_to_live_queue_when_open(app, call):
    call.set_field("program", "Graduate")

    app.on_escalate_handler(call)

    assert _transfer_numbers(call)[-1] == destinations.ROUTES[("Graduate", None, False)].number


def test_escalate_after_hours_reaches_higher_ed_default(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "after"
    mock = MockCall()
    app.on_call_start(mock)
    mock.set_field("program", "Graduate")

    app.on_escalate_handler(mock)

    assert _transfer_numbers(mock)[-1] == destinations.FALLBACK.number


def _continue_field(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    return next(item for item in task.action_items if getattr(item, "key", None) == "continue_with")


def test_hours_gate_offers_queue_option_when_open(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "open"
    mock = MockCall()
    app.on_call_start(mock)

    assert _continue_field(mock).choices == [
        "Be connected to our virtual assistant",
        "Be transferred to a queue to talk to a person",
    ]


def test_hours_gate_offers_voicemail_after_hours(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "after"
    mock = MockCall()
    app.on_call_start(mock)

    assert _continue_field(mock).choices == [
        "Be connected to our virtual assistant",
        "Leave a voicemail",
    ]


def test_greeting_is_the_first_checklist_item(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    assert task.action_items[0].item_type == "say"
    assert task.action_items[0].key == "greeting"


def _closed_notice_say(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    return next(item for item in task.action_items if getattr(item, "key", None) == "closed_notice")


def test_holiday_after_hours_names_the_holiday(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "after"
    app.settings.FORCE_HOLIDAY_NAME = "Winter Break"
    try:
        mock = MockCall()
        app.on_call_start(mock)
        assert "in observance of Winter Break" in _closed_notice_say(mock).statement
    finally:
        app.settings.FORCE_HOLIDAY_NAME = ""


def test_plain_after_hours_has_no_holiday_wording(app):
    app.settings.FORCE_HOURS = "after"

    from guava.testing import MockCall
    mock = MockCall()
    app.on_call_start(mock)
    say = _closed_notice_say(mock)

    assert "in observance of" not in say.statement
    assert "currently closed" in say.statement
