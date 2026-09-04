"""One test per named Grace destination, plus the hours-gate and greeting guardrails.

See destinations.py. Parametrization iterates destinations.ROUTES directly so this
list can never drift from the routing table.
"""

import pytest

import destinations


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
    "continue_with,expected",
    list(destinations.ROUTES.items()),
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values()],
)
def test_route_reaches_its_grace_destination(app, call, continue_with, expected):
    call.set_field("continue_with", continue_with)

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == expected.number


@pytest.mark.parametrize(
    "continue_with,expected",
    list(destinations.ROUTES.items()),
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values()],
)
def test_transfer_message_carries_an_immediacy_directive(app, call, continue_with, expected):
    call.set_field("continue_with", continue_with)

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


def _continue_field(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    return next(item for item in task.action_items if getattr(item, "key", None) == "continue_with")


def test_hours_gate_offers_live_team_member_when_open(app):
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
        "Receive a text message",
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


def _set_task_commands(call, task_id=None):
    cmds = [c for c in call._command_queue if type(c).__name__ == "SetTaskCommand"]
    if task_id is not None:
        cmds = [c for c in cmds if c.task_id == task_id]
    return cmds


def test_text_message_choice_never_transfers_and_starts_second_task(app, call):
    call.set_field("continue_with", "Receive a text message")

    app.on_route_complete(call)

    assert not any(type(c).__name__ == "TransferCommand" for c in call._command_queue)
    assert len(_set_task_commands(call, task_id="text_message")) == 1


def test_text_message_complete_sends_servicenow_link_for_current_students(app, call, monkeypatch):
    sent_calls = []
    monkeypatch.setattr(app.sms, "send_link", lambda *a, **k: sent_calls.append(a) or True)
    call.set_field("student_status", "Yes")

    app.on_text_message_complete(call)

    assert not any(type(c).__name__ == "TransferCommand" for c in call._command_queue)
    assert len(sent_calls) == 1
    assert sent_calls[0][1] == app.settings.K12_SERVICENOW_PORTAL_URL


def test_text_message_complete_sends_rfi_link_for_non_students(app, call, monkeypatch):
    sent_calls = []
    monkeypatch.setattr(app.sms, "send_link", lambda *a, **k: sent_calls.append(a) or True)
    call.set_field("student_status", "No")

    app.on_text_message_complete(call)

    assert not any(type(c).__name__ == "TransferCommand" for c in call._command_queue)
    assert len(sent_calls) == 1
    assert sent_calls[0][1] == app.settings.K12_RFI_FORM_URL
