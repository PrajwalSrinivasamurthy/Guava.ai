"""One test per named Grace destination (including the no-transfer enrollment path), plus the
hours-gate and greeting guardrails.

See destinations.py. Parametrization iterates destinations._routes() directly so this
list can never drift from the routing table.
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


def _set_task_commands(call, task_id=None):
    cmds = [c for c in call._command_queue if type(c).__name__ == "SetTaskCommand"]
    if task_id is not None:
        cmds = [c for c in cmds if c.task_id == task_id]
    return cmds


@pytest.mark.parametrize(
    "next_step,expected",
    [(k, v) for k, v in _ROUTES.items() if v.number is not None],
    ids=[dest.grace_outcome for dest in _ROUTES.values() if dest.number is not None],
)
def test_route_reaches_its_grace_destination(app, call, next_step, expected):
    call.set_field("next_step", next_step)

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == expected.number


@pytest.mark.parametrize(
    "next_step,expected",
    [(k, v) for k, v in _ROUTES.items() if v.number is not None],
    ids=[dest.grace_outcome for dest in _ROUTES.values() if dest.number is not None],
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


def test_enroll_complete_hangs_up_without_transferring(app, call, monkeypatch):
    monkeypatch.setattr(app.power_automate, "send_lead", lambda *a, **k: True)

    app.on_enroll_complete(call)

    assert _transfer_numbers(call) == []
    assert any(type(c).__name__ == "SendInstructionCommand" for c in call._command_queue)


def test_enroll_complete_pushes_the_collected_fields_to_power_automate(app, call, monkeypatch):
    call.set_field("first_name", "Jamie")
    call.set_field("last_name", "Rivera")
    call.set_field("email", "jamie@example.com")
    call.set_field("phone_number", "806-555-0100")
    call.set_field("college_credits", 45)
    call.set_field("enrollment_interested", "Yes")

    sent = {}
    monkeypatch.setattr(
        app.power_automate, "send_lead",
        lambda call, fields: sent.update(fields) or True,
    )

    app.on_enroll_complete(call)

    assert sent["first_name"] == "Jamie"
    assert sent["last_name"] == "Rivera"
    assert sent["email"] == "jamie@example.com"
    assert sent["phone_number"] == "806-555-0100"
    assert sent["college_credits"] == 45
    assert sent["enrollment_interested"] == "Yes"


def test_send_lead_maps_fields_to_the_power_automate_flow_s_expected_keys(app, monkeypatch):
    from guava.testing import MockCall

    posted = {}

    class _FakeResponse:
        status_code = 200
        text = "OK"

        def raise_for_status(self):
            pass

    def _fake_post(url, json, headers, timeout):
        posted["url"] = url
        posted["json"] = json
        posted["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr(app.power_automate.httpx, "post", _fake_post)

    mock = MockCall()
    fields = {
        "marketing_source": "Social media",
        "enrollment_interested": "Yes",
        "first_name": "Jamie",
        "last_name": "Rivera",
        "phone_number": "806-555-0100",
        "email": "jamie@example.com",
        "contact_preference": "Email",
        "college_credits": 45,
        "location": "Dallas",
        "willing_to_travel": "Yes",
    }

    assert app.power_automate.send_lead(mock, fields) is True
    assert posted["url"] == app.settings.TENK_POWER_AUTOMATE_URL
    assert posted["json"] == {
        "PhoneNumber": mock.call_info.from_number,
        "MarketingSource": "Social media",
        "EnrollmentInterest": "Yes",
        "CallerFirstName": "Jamie",
        "CallerLastName": "Rivera",
        "Email": "jamie@example.com",
        "CollectedNumber": "806-555-0100",
        "ContactPref": "Email",
        "CollegeCredits": "45",
        "Location": "Dallas",
        "WillingToTravel": "Yes",
    }


def test_send_lead_returns_false_without_raising_on_failure(app, monkeypatch):
    """Retry/backoff coverage for send_lead() lives in test_power_automate.py; this just
    checks the outward contract (False, never raises) still holds once every attempt fails."""
    from guava.testing import MockCall

    def _raise(*a, **k):
        raise Exception("boom")

    monkeypatch.setattr(app.power_automate.httpx, "post", _raise)
    monkeypatch.setattr(app.power_automate.time, "sleep", lambda seconds: None)

    assert app.power_automate.send_lead(MockCall(), {}) is False


def test_unrecognized_next_step_falls_back_to_live_queue(app, call):
    """next_step is a fixed-choice field, but the model isn't guaranteed to return an
    exact match — garbled free text should route to a human instead of crashing the
    call-handling callback with an AttributeError on a None destination."""
    call.set_field("next_step", "some unexpected free-text value")

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == _FALLBACK.number


def test_fallback_transfer_message_carries_an_immediacy_directive(app, call):
    call.set_field("next_step", "some unexpected free-text value")

    app.on_route_complete(call)

    xfer = _transfers(call)[-1]
    assert xfer.soft_transfer is True
    assert _ends_with_transfer_directive(xfer.transfer_message), xfer.transfer_message


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


def test_checklist_never_has_two_consecutive_says(app):
    """Regression guard: a second back-to-back Say item creates a seam a live call can slip
    an off-script turn into — closed-hours wording must fold into the single greeting Say."""
    from guava.testing import MockCall

    for hours in ("open", "after"):
        app.settings.FORCE_HOURS = hours
        mock = MockCall()
        app.on_call_start(mock)
        task = next(c for c in mock._command_queue if type(c).__name__ == "SetTaskCommand" and c.task_id == "route")
        says = [item for item in task.action_items if getattr(item, "item_type", None) == "say"]
        assert len(says) == 1, f"expected exactly one Say (hours={hours!r}), got {says}"


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
    call.set_field("next_step", "Be transferred to a queue to talk to a person")

    app.on_route_complete(call)

    assert _transfer_numbers(call)[-1] == "+19995550100"
