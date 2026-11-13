import logging

import pytest
from fastapi.testclient import TestClient

from kb_service.app import create_app
from kb_service.auth import ApiKeyVerifier, hash_key
from kb_service.domain import Answer
from kb_service.ratelimit import RateLimiter

_KEY = "test-key"
_AUTH = {"Authorization": f"Bearer {_KEY}"}
_QUESTION = "my very private question 8675309"


class _Answerer:
    def __init__(self, result=Answer(found=True, text="Use the bookstore."), error=None):
        self.result, self.error, self.questions = result, error, []

    def answer(self, question):
        self.questions.append(question)
        if self.error:
            raise self.error
        return self.result


def _client(answerer=None, limit=100, max_chars=500):
    app = create_app(
        answerer or _Answerer(), ApiKeyVerifier((hash_key(_KEY),)), RateLimiter(limit), max_question_chars=max_chars
    )
    return TestClient(app)


def test_a_valid_request_returns_the_answer():
    answerer = _Answerer()

    response = _client(answerer).post("/answer", json={"question": "Where are books?"}, headers=_AUTH)

    assert response.status_code == 200
    assert response.json() == {"found": True, "text": "Use the bookstore."}
    assert answerer.questions == ["Where are books?"]


def test_not_found_is_a_normal_response():
    client = _client(_Answerer(Answer.not_found()))

    response = client.post("/answer", json={"question": "Unrelated?"}, headers=_AUTH)

    assert response.status_code == 200
    assert response.json() == {"found": False, "text": ""}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": _KEY}, {"Authorization": "Basic abc"}])
def test_requests_without_a_valid_key_are_refused(headers):
    answerer = _Answerer()

    response = _client(answerer).post("/answer", json={"question": "Hi?"}, headers=headers)

    assert response.status_code == 401
    assert answerer.questions == []


def test_the_key_is_checked_before_the_body():
    response = _client().post("/answer", json={}, headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 11}])
def test_an_invalid_question_is_rejected(body):
    response = _client(max_chars=10).post("/answer", json=body, headers=_AUTH)

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid request"}


def test_a_rejected_question_is_not_echoed_back():
    response = _client(max_chars=10).post("/answer", json={"question": _QUESTION}, headers=_AUTH)

    assert response.status_code == 422
    assert _QUESTION not in response.text


def test_requests_over_the_rate_limit_get_429():
    client = _client(limit=2)

    statuses = [client.post("/answer", json={"question": "Hi?"}, headers=_AUTH).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


def test_a_failure_while_answering_returns_503_without_details():
    client = _client(_Answerer(error=RuntimeError("database exploded")))

    response = client.post("/answer", json={"question": _QUESTION}, headers=_AUTH)

    assert response.status_code == 503
    assert "exploded" not in response.text and _QUESTION not in response.text


def test_health_needs_no_key_and_the_docs_pages_are_off():
    client = _client()

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


@pytest.mark.parametrize("failing", [False, True])
def test_the_question_text_never_reaches_the_logs(caplog, failing):
    client = _client(_Answerer(error=RuntimeError("boom") if failing else None))

    with caplog.at_level(logging.DEBUG):
        client.post("/answer", json={"question": _QUESTION}, headers=_AUTH)

    assert caplog.records
    assert _QUESTION not in caplog.text and "8675309" not in caplog.text
