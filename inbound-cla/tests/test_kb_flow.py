"""The flow where the agent answers questions itself (app.kb set), as opposed to handing
callers to the virtual assistant. Offline: the knowledge service is a fake."""

import logging

import pytest
from guava.testing import MockCall
from kb_client import KbAnswer, KbUnavailable

import assist

_QUESTION = "my very private question 8675309"


class _FakeKb:
    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.questions = answer, error, []

    def ask(self, question):
        self.questions.append(question)
        if self.error:
            raise self.error
        return self.answer


@pytest.fixture
def kb(app, monkeypatch):
    fake = _FakeKb(KbAnswer(found=True, text="Buy them at the bookstore."))
    monkeypatch.setattr(app, "kb", fake)
    return fake


def _commands(call, kind):
    return [c for c in call._command_queue if type(c).__name__ == kind]


def _task(call):
    return _commands(call, "SetTaskCommand")[-1]


def _start(app, hours):
    app.settings.FORCE_HOURS = hours
    call = MockCall()
    app.on_call_start(call)
    return call


def _outcome_field(call):
    return next(item for item in _task(call).action_items if getattr(item, "key", None) == "outcome")


def _greeting(call):
    return next(item for item in _task(call).action_items if getattr(item, "key", None) == "greeting").statement


def test_call_start_sets_the_assist_task_not_the_route_task(app, kb):
    call = _start(app, "open")

    assert _task(call).task_id == "assist"


def test_open_hours_offers_a_person_or_no_more_questions(app, kb):
    assert _outcome_field(_start(app, "open")).choices == [assist.TRANSFER, assist.DONE]


def test_after_hours_offers_voicemail_text_and_no_more_questions(app, kb):
    assert _outcome_field(_start(app, "after")).choices == [assist.VOICEMAIL, assist.TEXT_MESSAGE, assist.DONE]


def test_the_text_option_is_dropped_when_no_link_is_configured(app, kb, monkeypatch):
    monkeypatch.setattr(app.settings, "CLA_AH_TEXT_URL", "")

    call = _start(app, "after")

    assert _outcome_field(call).choices == [assist.VOICEMAIL, assist.DONE]
    assert "text message" not in _greeting(call)


def test_the_virtual_assistant_is_never_offered_as_a_destination(app, kb):
    for hours in ("open", "after"):
        call = _start(app, hours)

        assert not any("assistant" in choice.lower() for choice in _outcome_field(call).choices)
        assert "transfer you to our virtual assistant" not in _greeting(call)


def test_the_greeting_offers_questions_and_the_support_center(app, kb):
    greeting = _greeting(_start(app, "open"))

    assert "Career Learning Academy" in greeting and "answer your questions" in greeting
    assert "support center" in greeting and "may be recorded" in greeting


def test_a_holiday_is_named_after_hours(app, kb, monkeypatch):
    monkeypatch.setattr(app.settings, "FORCE_HOLIDAY_NAME", "Winter Break")

    assert "in observance of Winter Break" in _greeting(_start(app, "after"))


def test_the_checklist_never_has_two_consecutive_says(app, kb):
    for hours in ("open", "after"):
        items = _task(_start(app, hours)).action_items
        kinds = [getattr(item, "item_type", None) for item in items]

        assert "say" not in [a for a, b in zip(kinds, kinds[1:]) if a == b]


@pytest.mark.parametrize("outcome", [assist.TRANSFER, assist.VOICEMAIL])
def test_asking_for_a_person_transfers_to_the_support_center(app, kb, outcome):
    call = MockCall()
    call.set_field("outcome", outcome)

    app.on_assist_complete(call)

    transfer = _commands(call, "TransferCommand")[-1]
    assert transfer.to_number == app.settings.LIVE_NUMBER
    assert "our support center" in transfer.transfer_message
    assert "Career Learning Academy" not in transfer.transfer_message
    assert transfer.transfer_message.rstrip(".").lower().endswith("then transfer")


def test_no_more_questions_says_goodbye_without_transferring(app, kb):
    call = MockCall()
    call.set_field("outcome", assist.DONE)

    app.on_assist_complete(call)

    assert _commands(call, "TransferCommand") == []
    assert _commands(call, "SendInstructionCommand")


def test_the_text_choice_sends_the_link_and_never_transfers(app, kb, monkeypatch):
    sent = []
    monkeypatch.setattr(app.sms, "send_link", lambda *args: sent.append(args) or True)
    call = MockCall()
    call.set_field("outcome", assist.TEXT_MESSAGE)

    app.on_assist_complete(call)

    assert len(sent) == 1 and sent[0][1] == app.settings.CLA_AH_TEXT_URL
    assert _commands(call, "TransferCommand") == []


def test_an_unrecognized_outcome_falls_back_to_the_support_center(app, kb):
    call = MockCall()

    app.on_assist_complete(call)

    assert _commands(call, "TransferCommand")[-1].to_number == app.settings.LIVE_NUMBER


def test_a_missing_support_center_number_hangs_up_instead_of_transferring(app, kb, monkeypatch):
    empty = {attr: "" for attr in app.live_config._NUMBER_MAPPING}
    monkeypatch.setattr(app.live_config, "_current", app.live_config.LiveConfig(document_qa=None, numbers=empty))
    call = MockCall()
    call.set_field("outcome", assist.TRANSFER)

    app.on_assist_complete(call)

    assert _commands(call, "TransferCommand") == []


def test_a_found_answer_is_spoken(app, kb):
    assert app.on_question(MockCall(), "Where are books?") == "Buy them at the bookstore."
    assert kb.questions == ["Where are books?"]


def test_no_answer_gives_the_fallback_message(app, kb):
    kb.answer = KbAnswer(found=False)

    assert app.on_question(MockCall(), "Unrelated?") == app.settings.KB_FALLBACK_MESSAGE


def test_an_unavailable_service_gives_the_fallback_message(app, kb):
    kb.error = KbUnavailable("Timeout")

    assert app.on_question(MockCall(), "Where are books?") == app.settings.KB_FALLBACK_MESSAGE


def test_the_fallback_message_offers_the_support_center_and_more_questions(app):
    message = app.settings.KB_FALLBACK_MESSAGE

    assert "don't have an answer" in message and "support center" in message
    assert "ask me something else" in message


@pytest.mark.parametrize("failing", [False, True])
def test_the_question_text_is_never_logged(app, kb, caplog, failing):
    if failing:
        kb.error = KbUnavailable("Timeout")

    with caplog.at_level(logging.DEBUG):
        app.on_question(MockCall(), _QUESTION)

    assert "8675309" not in caplog.text


def test_the_question_text_is_never_logged_without_the_knowledge_service(app, caplog):
    with caplog.at_level(logging.DEBUG):
        app.on_question(MockCall(), _QUESTION)

    assert "8675309" not in caplog.text
