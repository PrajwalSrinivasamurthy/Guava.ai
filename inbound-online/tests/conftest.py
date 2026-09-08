"""Shared fixtures. Loads __main__.py as the importable module `app`.

Offline only — no network, no LLM. destinations.py drives every routing decision as a plain
data lookup, so the whole suite exercises it (and the on_call_start / on_route_complete wiring
around it) by calling handlers directly on a MockCall.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
# .env/.env.example name this GUAVA_LOCAL_API_KEY; the vendored SDK's Client only ever
# reads GUAVA_API_KEY (see guava/client.py), so mirror it across before anything
# constructs a Client. Falls back to a harmless placeholder so offline tests never need
# a real key.
os.environ.setdefault("GUAVA_API_KEY", os.environ.get("GUAVA_LOCAL_API_KEY") or "test-key")
os.environ.setdefault("GUAVA_AGENT_NUMBER", "+18065154465")


def _load():
    sys.path.insert(0, str(_ROOT))
    spec = importlib.util.spec_from_file_location("app", _ROOT / "__main__.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["app"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def app():
    return _load()


@pytest.fixture(autouse=True)
def _hours_open(app):
    """Default every test to business-hours-open; individual tests override before
    calling on_call_start when they need the after-hours branch."""
    app.settings.FORCE_HOURS = "open"
    yield
    app.settings.FORCE_HOURS = "open"


@pytest.fixture(autouse=True)
def _no_real_document_qa(app, monkeypatch):
    """Belt and braces: no test path should ever reach the real RAG service."""
    class _FakeDocumentQA:
        def ask(self, question: str) -> str:
            return "fake answer"

    monkeypatch.setattr(app, "_document_qa", _FakeDocumentQA())


@pytest.fixture
def call(app):
    """A MockCall with on_call_start already run, so the route task/Fields exist.

    Every handler under test reads that state, so building it by hand in each test
    would be both noise and a place for the tests to drift from the real call.
    """
    from guava.testing import MockCall
    mock = MockCall()
    app.on_call_start(mock)
    return mock


# ── Live tier (agent.test — scripted turn-by-turn) ────────────────────────────
#
# Everything above is offline/MockCall. This tier exercises the real Dialog Engine +
# LLM with EXACT scripted caller lines (never agent.roleplay()), so it's gated behind
# RUN_LIVE=1 and a real GUAVA_API_KEY via the `requires_live` skipif below, keeping the
# default `pytest` run offline and instant.
#
#   RUN_LIVE=1 uv run --env-file .env pytest tests/test_scripted.py -v

LIVE = (os.environ.get("RUN_LIVE") == "1"
        and os.environ.get("GUAVA_API_KEY", "test-key") != "test-key")

requires_live = pytest.mark.skipif(
    not LIVE, reason="set RUN_LIVE=1 and a real GUAVA_API_KEY to run live agent tests")

LIVE_RUNS = int(os.environ.get("LIVE_RUNS", "1"))  # optional repeat, for drift-checking
                                                    # a classifier-sensitive scripted line

_TRANSCRIPTS = Path(__file__).resolve().parent / "transcripts"


@pytest.fixture
def record():
    """Persist a live session's transcript for audit."""
    def _record(session, name):
        _TRANSCRIPTS.mkdir(exist_ok=True)
        transcript = session.get_transcript()
        reason = getattr(session, "termination_reason", None)
        (_TRANSCRIPTS / f"{name}.txt").write_text(
            f"# {name}\n## termination_reason: {reason!r}\n\n{transcript}\n")
        print(f"\n[{name}] termination_reason={reason!r}")
        return {"transcript": transcript, "termination_reason": reason}
    return _record
