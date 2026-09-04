"""One test per named Grace destination (including the no-transfer enrollment path), plus the
hours-gate and greeting guardrails.

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


def _set_task_commands(call, task_id=None):
    cmds = [c for c in call._command_queue if type(c).__name__ == "SetTaskCommand"]
    if task_id is not None:
        cmds = [c for c in cmds if c.task_id == task_id]
    return cmds


@pytest.mark.parametrize(
    "next_step,expected",
    [(k, v) for k, v in destinations.ROUTES.items() if v.number is not None],
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values() if dest.number is not None],
)
def test_route_reaches_its_grace_destination(app, call, next_step, expected):
    call.set_field("next_step", next_step)

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == expected.number


@pytest.mark.parametrize(
    "next_step,expected",
    [(k, v) for k, v in destinations.ROUTES.items() if v.number is not None],
    ids=[dest.grace_outcome for dest in destinations.ROUTES.values() if dest.number is not None],
)
def test_transfer_message_carries_an_immediacy_directive(app, call, next_step, expected):
    call.set_field("next_step", next_step)

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


def test_enrollment_path_never_transfers_and_starts_the_enroll_task(app, call):
    call.set_field("next_step", "Enroll in the program")

    app.on_route_complete(call)

    assert _transfer_numbers(call) == []
    assert len(_set_task_commands(call, task_id="enroll")) == 1


def test_enroll_complete_hangs_up_without_transferring(app, call):
    app.on_enroll_complete(call)

    assert _transfer_numbers(call) == []
    assert any(type(c).__name__ == "SendInstructionCommand" for c in call._command_queue)


def _next_step_field(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand" and c.task_id == "route")
    return next(item for item in task.action_items if getattr(item, "key", None) == "next_step")


def test_hours_gate_offers_live_agent_choices_when_open(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "open"
    mock = MockCall()
    app.on_call_start(mock)

    assert set(_next_step_field(mock).choices) == {"Be connected to our virtual assistant", "Be transferred to a queue to talk to a person"}


def test_hours_gate_offers_after_hours_choices_when_closed(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "after"
    mock = MockCall()
    app.on_call_start(mock)

    assert set(_next_step_field(mock).choices) == {"General information", "Enroll in the program", "Leave a voicemail"}


def test_greeting_is_the_first_checklist_item(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand" and c.task_id == "route")
    assert task.action_items[0].item_type == "say"
    assert task.action_items[0].key == "greeting"
