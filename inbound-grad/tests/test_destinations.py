"""One test per named Grace destination, plus the hours-gate and greeting guardrails.

Parametrization iterates destinations._routes() directly so this list can never drift
from the routing table.
"""

import pytest

import destinations
import live_config
import settings

_NUMBERS = {attr: getattr(settings, attr) for attr in live_config._NUMBER_MAPPING}
_ROUTES = destinations._routes(_NUMBERS)
_FALLBACK = destinations.fallback(_NUMBERS)


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
    list(_ROUTES.items()),
    ids=[dest.grace_outcome for dest in _ROUTES.values()],
)
def test_route_reaches_its_grace_destination(app, call, continue_with, expected):
    call.set_field("continue_with", continue_with)

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == expected.number


@pytest.mark.parametrize(
    "continue_with,expected",
    list(_ROUTES.items()),
    ids=[dest.grace_outcome for dest in _ROUTES.values()],
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


def _greeting_say(call):
    task = next(c for c in call._command_queue if type(c).__name__ == "SetTaskCommand")
    return next(item for item in task.action_items if getattr(item, "key", None) == "greeting")


def test_holiday_after_hours_names_the_holiday(app):
    from guava.testing import MockCall

    app.settings.FORCE_HOURS = "after"
    app.settings.FORCE_HOLIDAY_NAME = "Winter Break"
    try:
        mock = MockCall()
        app.on_call_start(mock)
        assert "in observance of Winter Break" in _greeting_say(mock).statement
    finally:
        app.settings.FORCE_HOLIDAY_NAME = ""


def test_plain_after_hours_has_no_holiday_wording(app):
    app.settings.FORCE_HOURS = "after"

    from guava.testing import MockCall
    mock = MockCall()
    app.on_call_start(mock)
    say = _greeting_say(mock)

    assert "in observance of" not in say.statement
    assert "currently closed" in say.statement


def test_open_hours_greeting_has_no_closed_wording(call):
    assert "currently closed" not in _greeting_say(call).statement


def test_checklist_never_has_two_consecutive_says(app):
    """Regression guard: a second back-to-back Say item creates a seam a live call can slip
    an off-script turn into — closed/holiday wording must fold into the single greeting Say."""
    from guava.testing import MockCall

    for hours, holiday in (("open", ""), ("after", ""), ("after", "Winter Break")):
        app.settings.FORCE_HOURS = hours
        app.settings.FORCE_HOLIDAY_NAME = holiday
        try:
            mock = MockCall()
            app.on_call_start(mock)
            task = next(c for c in mock._command_queue if type(c).__name__ == "SetTaskCommand")
            says = [item for item in task.action_items if getattr(item, "item_type", None) == "say"]
            assert len(says) == 1, f"expected exactly one Say (hours={hours!r}, holiday={holiday!r}), got {says}"
        finally:
            app.settings.FORCE_HOLIDAY_NAME = ""


def test_text_message_never_transfers_and_hangs_up(app, call, monkeypatch):
    sent_calls = []
    monkeypatch.setattr(app.sms, "send_link", lambda *a, **k: sent_calls.append(a) or True)
    call.set_field("continue_with", "Receive a text message")

    app.on_route_complete(call)

    assert not any(type(c).__name__ == "TransferCommand" for c in call._command_queue)
    assert any(type(c).__name__ == "SendInstructionCommand" for c in call._command_queue)
    assert len(sent_calls) == 1


def test_text_message_send_failure_still_hangs_up_without_transfer(app, call, monkeypatch):
    monkeypatch.setattr(app.sms, "send_link", lambda *a, **k: False)
    call.set_field("continue_with", "Receive a text message")

    app.on_route_complete(call)

    assert not any(type(c).__name__ == "TransferCommand" for c in call._command_queue)
    assert any(type(c).__name__ == "SendInstructionCommand" for c in call._command_queue)


def test_unrecognized_continue_with_falls_back_to_live_queue(app, call):
    """continue_with is a fixed-choice field, but the model isn't guaranteed to return an
    exact match — garbled free text should route to a human instead of crashing the
    call-handling callback with an AttributeError on a None destination."""
    call.set_field("continue_with", "some unexpected free-text value")

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == _FALLBACK.number


def test_fallback_transfer_message_carries_an_immediacy_directive(app, call):
    call.set_field("continue_with", "some unexpected free-text value")

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


def test_routes_reread_numbers_after_a_live_config_refresh(app, call, monkeypatch):
    """Regression guard: destinations._routes() must read numbers from
    live_config.get().numbers fresh on every resolve() call — the poller replaces
    live_config._current wholesale on every refresh cycle, and a routing table that
    captured a stale numbers dict at process start would silently ignore that."""
    current = app.live_config.get()
    changed_numbers = {**current.numbers, "LIVE_NUMBER": "+19995550100"}
    monkeypatch.setattr(
        app.live_config, "_current",
        app.live_config.LiveConfig(document_qa=current.document_qa, numbers=changed_numbers),
    )
    call.set_field("continue_with", "Be transferred to a queue to talk to a person")

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == "+19995550100"
