"""kb_client.KbClient against a fake session — no network."""

import pytest
import requests
from kb_client import KbAnswer, KbClient, KbUnavailable

_QUESTION = "my very private question 8675309"


class _Response:
    def __init__(self, status=200, body=None, bad_json=False):
        self.status_code = status
        self._body, self._bad_json = body, bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._body


class _Session:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def post(self, url, json, headers, timeout):
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.error:
            raise self.error
        return self.response


def _client(session, **kwargs):
    return KbClient("https://kb.example/cla-kb/", "secret-key", session=session, **kwargs)


def test_a_found_answer_is_returned():
    session = _Session(_Response(body={"found": True, "text": "Use the bookstore."}))

    assert _client(session).ask("Where are books?") == KbAnswer(found=True, text="Use the bookstore.")


def test_the_request_carries_the_key_the_timeout_and_the_question():
    session = _Session(_Response(body={"found": False, "text": ""}))

    _client(session, timeout_seconds=2.5).ask("Where are books?")

    call = session.calls[0]
    assert call["url"] == "https://kb.example/cla-kb/answer"
    assert call["headers"] == {"Authorization": "Bearer secret-key"}
    assert call["timeout"] == 2.5
    assert call["json"] == {"question": "Where are books?"}


def test_a_not_found_reply_is_a_normal_result():
    session = _Session(_Response(body={"found": False, "text": ""}))

    assert _client(session).ask("Unrelated?") == KbAnswer(found=False, text="")


def test_a_found_reply_with_no_text_counts_as_not_found():
    session = _Session(_Response(body={"found": True, "text": ""}))

    assert _client(session).ask("q").found is False


def test_long_questions_are_cut_to_the_service_limit():
    session = _Session(_Response(body={"found": False, "text": ""}))

    _client(session, max_question_chars=10).ask("x" * 50)

    assert session.calls[0]["json"] == {"question": "x" * 10}


@pytest.mark.parametrize("status", [401, 422, 429, 500, 503])
def test_a_bad_status_is_unavailable(status):
    with pytest.raises(KbUnavailable, match=str(status)):
        _client(_Session(_Response(status=status))).ask("q")


@pytest.mark.parametrize("response", [
    _Response(bad_json=True),
    _Response(body={"unexpected": 1}),
    _Response(body=["not", "an", "object"]),
])
def test_a_malformed_reply_is_unavailable(response):
    with pytest.raises(KbUnavailable, match="malformed"):
        _client(_Session(response)).ask("q")


@pytest.mark.parametrize("error", [requests.Timeout("slow"), requests.ConnectionError("refused")])
def test_network_failures_are_unavailable_and_never_mention_the_question(error):
    with pytest.raises(KbUnavailable) as raised:
        _client(_Session(error=error)).ask(_QUESTION)

    assert type(error).__name__ in str(raised.value)
    assert _QUESTION not in str(raised.value) and "8675309" not in repr(raised.value.__cause__)
