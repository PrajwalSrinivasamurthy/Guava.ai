"""
Live, periodically-refreshed snapshot of Google Sheet config (FAQ content + shared
phone numbers), replacing the old load-once-per-process behavior.

    init()          — build the first snapshot. Called once, at import time, before
                       `destinations` reads any phone-number settings.
    start_poller()  — spawn a daemon thread that rebuilds the snapshot every
                       settings.CONFIG_POLL_SECONDS, so sheet edits show up without a
                       redeploy. Only called from `if __name__ == "__main__":` (never
                       during tests/imports).
    get()           — read the current snapshot. Cheap, thread-safe (a single
                       reference reassignment is atomic under the GIL): always
                       returns a fully-built LiveConfig, never a half-updated one.

Failure handling: any load failure (network, bad credentials, empty tab) falls back to
the last cache the corresponding config_sheet.py function can find; the in-memory
snapshot is only replaced once a build fully succeeds, so a broken refresh never
degrades what's already being served. Poll failures are logged and reported via
chat_notify (a no-op unless GOOGLE_CHAT_WEBHOOK_URL is set); they never crash the
process.
"""

import logging
import threading
import time
import types
from dataclasses import dataclass

import chat_notify
from guava.helpers.rag import DocumentQA

import config_sheet
import settings

logger = logging.getLogger(__name__)

# {settings attr: "Shared Config" sheet key} — same mapping __main__.py used to pass to
# config_sheet.apply_numbers() once at import; now re-applied on every poll too.
_NUMBER_MAPPING = {
    "LIVE_NUMBER": "grad_live",
    "ELEVENLABS_NUMBER": "grad_elevenlabs",
}

_NAMESPACE = "texas-tech-grad"

# Overrides DocumentQA's default instructions, which literally tell the model to
# say "the answer is not in the provided context" when it can't find one — that
# leaked to a caller verbatim. This phrasing keeps
# the caller-facing decline natural and routes them onward instead.
_DOCUMENT_QA_INSTRUCTIONS = (
    f"You are a phone agent for {settings.ORGANIZATION_NAME}. Answer the caller's "
    "question using ONLY the provided document excerpts, in natural spoken "
    "language — never mention documents, context, or a knowledge base. If the "
    "answer isn't in the excerpts, say you don't have that information on hand "
    "and offer to connect them with a live team member. Do not offer any "
    "follow-ups."
)


@dataclass(frozen=True)
class LiveConfig:
    document_qa: DocumentQA | None
    numbers: dict[str, str]  # {settings attr name: current value}, e.g. {"LIVE_NUMBER": "+1..."}


_current: LiveConfig | None = None
_last_corpus: str | None = None


def get() -> LiveConfig:
    if _current is None:
        raise RuntimeError("live_config.init() has not been called yet")
    return _current


def _build(require_sheet: bool = False) -> LiveConfig:
    global _last_corpus

    faqs = config_sheet.load(settings.FAQ_SPREADSHEET_ID, require_sheet=require_sheet)

    try:
        numbers = config_sheet.refresh_numbers(settings.FAQ_SPREADSHEET_ID)
        config_sheet.save_cache(numbers=numbers)
    except Exception as exc:
        if require_sheet:
            raise
        logger.warning("Could not refresh phone numbers from sheet, keeping cached values: %s", exc)
    # apply_numbers() itself is unchanged — only the object it mutates changes, from the
    # shared settings module to a disposable local namespace seeded with settings.py's
    # own hardcoded defaults, so a key missing from the cache still resolves correctly.
    _numbers_target = types.SimpleNamespace(**{attr: getattr(settings, attr) for attr in _NUMBER_MAPPING})
    config_sheet.apply_numbers(_numbers_target, _NUMBER_MAPPING)
    numbers_snapshot = {attr: getattr(_numbers_target, attr) for attr in _NUMBER_MAPPING}

    corpus = config_sheet.render_corpus(faqs)
    if _current is not None and corpus == _last_corpus:
        # Unchanged since the last successful build — skip re-ingesting the corpus into
        # DocumentQA (a live network call) on every poll tick. Still return a FRESH
        # LiveConfig carrying numbers_snapshot: numbers refresh independently of corpus
        # content, so reusing `_current` wholesale here would freeze numbers at their
        # last value until the corpus itself next changes.
        return LiveConfig(document_qa=_current.document_qa, numbers=numbers_snapshot)

    document_qa = DocumentQA(
        documents=corpus,
        namespace=_NAMESPACE,
        instructions=_DOCUMENT_QA_INSTRUCTIONS,
    )
    _last_corpus = corpus
    return LiveConfig(document_qa=document_qa, numbers=numbers_snapshot)


def init(require_sheet: bool = False) -> None:
    """Build the first snapshot. Never blocks/crashes startup on a Sheets outage:
    falls back to LiveConfig(document_qa=None, numbers=<settings.py's hardcoded
    defaults>) if even the local cache is missing, matching the previous
    lazy-singleton's graceful degradation — routing must keep working even when the
    knowledge base fails to load."""
    global _current
    try:
        _current = _build(require_sheet=require_sheet)
    except Exception as exc:
        logger.warning("Could not load %s knowledge base: %s", settings.ORGANIZATION_NAME, exc)
        _current = LiveConfig(
            document_qa=None,
            numbers={attr: getattr(settings, attr) for attr in _NUMBER_MAPPING},
        )


def start_poller(interval_seconds: int = 60) -> None:
    def _poll():
        while True:
            time.sleep(interval_seconds)
            try:
                global _current
                _current = _build(require_sheet=False)
                logger.info("live_config refreshed.")
            except Exception as exc:
                logger.warning("live_config refresh failed — keeping previous config: %s", exc)
                chat_notify.notify(
                    f"live_config refresh failed — keeping previous in-memory config: {exc}",
                    project_name=settings.ORGANIZATION_NAME,
                )

    threading.Thread(target=_poll, daemon=True, name="live-config-poller").start()
