import logging
import threading

from kb_service.warmup import KeepWarm


def test_it_pings_at_once_and_then_repeatedly_until_stopped():
    pings, enough = [], threading.Event()

    def ping():
        pings.append(1)
        if len(pings) >= 3:
            enough.set()

    warm = KeepWarm(ping, 0.01)
    warm.start()
    assert enough.wait(2)
    warm.stop()

    seen = len(pings)
    threading.Event().wait(0.05)
    assert len(pings) == seen


def test_a_failing_ping_does_not_stop_the_loop_and_logs_only_the_error_type(caplog):
    calls, retried = [], threading.Event()

    def ping():
        calls.append(1)
        if len(calls) >= 2:
            retried.set()
        raise RuntimeError("detail that should not be logged 8675309")

    with caplog.at_level(logging.WARNING, logger="kb_service.warmup"):
        warm = KeepWarm(ping, 0.01)
        warm.start()
        assert retried.wait(2)
        warm.stop()

    assert "RuntimeError" in caplog.text
    assert "8675309" not in caplog.text


def test_stop_returns_promptly_even_with_a_long_interval():
    warm = KeepWarm(lambda: None, 3600)
    warm.start()

    warm.stop()

    assert not warm._thread.is_alive()
