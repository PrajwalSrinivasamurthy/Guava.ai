"""Coverage for power_automate.send_lead()'s retry/backoff behavior. Field-mapping and
the one-shot failure contract (returns False, never raises) are covered in
test_destinations.py; this file is scoped to the retry logic layered on top of it.
"""

import httpx
import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep(app, monkeypatch):
    """Retries sleep for real between attempts — patch it out so this suite stays instant."""
    monkeypatch.setattr(app.power_automate.time, "sleep", lambda seconds: None)


def _response(status_code, url="https://example.com/pa"):
    return httpx.Response(status_code, request=httpx.Request("POST", url))


def test_retries_on_connection_error_then_succeeds(app, monkeypatch):
    from guava.testing import MockCall

    attempts = []

    def _fake_post(url, json, headers, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise httpx.ConnectError("connection refused")
        return _response(200)

    monkeypatch.setattr(app.power_automate.httpx, "post", _fake_post)

    assert app.power_automate.send_lead(MockCall(), {}) is True
    assert len(attempts) == 3


def test_gives_up_after_max_attempts_on_persistent_failure(app, monkeypatch):
    from guava.testing import MockCall

    attempts = []

    def _fake_post(url, json, headers, timeout):
        attempts.append(1)
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(app.power_automate.httpx, "post", _fake_post)

    assert app.power_automate.send_lead(MockCall(), {}) is False
    assert len(attempts) == app.power_automate._MAX_ATTEMPTS


def test_retries_on_5xx_response(app, monkeypatch):
    from guava.testing import MockCall

    attempts = []

    def _fake_post(url, json, headers, timeout):
        attempts.append(1)
        return _response(503) if len(attempts) < 2 else _response(200)

    monkeypatch.setattr(app.power_automate.httpx, "post", _fake_post)

    assert app.power_automate.send_lead(MockCall(), {}) is True
    assert len(attempts) == 2


def test_does_not_retry_on_4xx_response(app, monkeypatch):
    """A 4xx means the flow rejected the request itself (bad payload/auth) — retrying
    the exact same body won't help, so this should fail fast on the first attempt."""
    from guava.testing import MockCall

    attempts = []

    def _fake_post(url, json, headers, timeout):
        attempts.append(1)
        return _response(400)

    monkeypatch.setattr(app.power_automate.httpx, "post", _fake_post)

    assert app.power_automate.send_lead(MockCall(), {}) is False
    assert len(attempts) == 1


def test_logs_request_body_and_response(app, monkeypatch, caplog):
    from guava.testing import MockCall

    monkeypatch.setattr(app.power_automate.httpx, "post", lambda *a, **k: _response(200))

    with caplog.at_level("INFO", logger="power_automate"):
        assert app.power_automate.send_lead(MockCall(), {"first_name": "Jamie"}) is True

    messages = [r.message for r in caplog.records]
    assert any("request body" in m and "Jamie" in m for m in messages)
    assert any("response" in m and "status=200" in m for m in messages)


def test_backoff_doubles_between_attempts(app, monkeypatch):
    from guava.testing import MockCall

    sleeps = []
    monkeypatch.setattr(app.power_automate.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(
        app.power_automate.httpx, "post",
        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("connection refused")),
    )

    assert app.power_automate.send_lead(MockCall(), {}) is False
    assert sleeps == [1, 2]
