"""Unit tests for live_config's build/init behavior — the fallback-on-failure and
skip-rebuild-when-unchanged logic that config_sheet.py's load()/refresh_numbers()/
apply_numbers() feed into. All network-touching config_sheet functions are
monkeypatched directly, so nothing here hits a real sheet or the RAG service.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_last_corpus(app, monkeypatch):
    """live_config._current is already isolated per-test by conftest's
    _no_real_document_qa fixture; _last_corpus isn't, so reset it here too."""
    monkeypatch.setattr(app.live_config, "_last_corpus", None)


class _FakeDocumentQA:
    def __init__(self, documents, namespace, instructions):
        self.documents = documents
        self.namespace = namespace
        self.instructions = instructions

    def ask(self, question: str) -> str:
        return "fake answer"


_FAKE_FAQS = [{"category": "General", "question": "q", "answer": "a"}]


def test_build_falls_back_when_number_refresh_fails(app, monkeypatch):
    """FAQ load succeeds but the live number refresh fails (e.g. sheet outage) —
    _build(require_sheet=False) must not raise; apply_numbers() falls back to
    whatever's cached on its own."""
    monkeypatch.setattr(app.live_config, "DocumentQA", _FakeDocumentQA)
    monkeypatch.setattr(app.live_config.config_sheet, "load", lambda *a, **k: _FAKE_FAQS)
    monkeypatch.setattr(app.live_config.config_sheet, "refresh_numbers",
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sheet down")))
    monkeypatch.setattr(app.live_config.config_sheet, "apply_numbers", lambda *a, **k: None)

    config = app.live_config._build(require_sheet=False)

    assert config.document_qa is not None
    assert config.document_qa.ask("anything") == "fake answer"


def test_build_require_sheet_propagates_number_refresh_failure(app, monkeypatch):
    """During the deploy-time / first-boot require_sheet=True path, a broken number
    refresh must be visible (raise), not silently swallowed."""
    monkeypatch.setattr(app.live_config, "DocumentQA", _FakeDocumentQA)
    monkeypatch.setattr(app.live_config.config_sheet, "load", lambda *a, **k: _FAKE_FAQS)
    monkeypatch.setattr(app.live_config.config_sheet, "refresh_numbers",
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sheet down")))

    with pytest.raises(RuntimeError):
        app.live_config._build(require_sheet=True)


def test_build_skips_rebuilding_document_qa_when_corpus_unchanged(app, monkeypatch):
    """DocumentQA construction is a live network call — must not repeat it on every
    poll tick when the FAQ content hasn't actually changed."""
    build_calls = []

    class _CountingDocumentQA(_FakeDocumentQA):
        def __init__(self, *a, **k):
            build_calls.append(1)
            super().__init__(*a, **k)

    monkeypatch.setattr(app.live_config, "DocumentQA", _CountingDocumentQA)
    monkeypatch.setattr(app.live_config.config_sheet, "load", lambda *a, **k: _FAKE_FAQS)
    monkeypatch.setattr(app.live_config.config_sheet, "refresh_numbers", lambda *a, **k: {})
    monkeypatch.setattr(app.live_config.config_sheet, "save_cache", lambda *a, **k: None)
    monkeypatch.setattr(app.live_config.config_sheet, "apply_numbers", lambda *a, **k: None)

    first = app.live_config._build(require_sheet=False)
    monkeypatch.setattr(app.live_config, "_current", first)  # mirrors what init()/the poller do
    second = app.live_config._build(require_sheet=False)

    assert len(build_calls) == 1
    # Not `second is first`: _build() always returns a fresh LiveConfig so numbers can
    # refresh independently of corpus content — only the (expensive) document_qa object
    # itself is reused when the corpus hasn't changed.
    assert second.document_qa is first.document_qa


def test_init_degrades_to_no_knowledge_base_instead_of_raising(app, monkeypatch):
    """First boot with an unreachable sheet AND no local cache at all: init() must
    never crash the process — it degrades to document_qa=None, matching the old lazy
    singleton's graceful degradation."""
    monkeypatch.setattr(app.live_config.config_sheet, "load",
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no sheet, no cache")))
    monkeypatch.setattr(app.live_config.config_sheet, "refresh_numbers",
                         lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no sheet")))
    monkeypatch.setattr(app.live_config.config_sheet, "apply_numbers", lambda *a, **k: None)

    app.live_config.init()

    assert app.live_config.get().document_qa is None
    # Routing must keep working even when the knowledge base fails to load.
    assert app.live_config.get().numbers


def test_get_raises_before_init_has_run(app, monkeypatch):
    monkeypatch.setattr(app.live_config, "_current", None)

    with pytest.raises(RuntimeError):
        app.live_config.get()


def test_build_never_mutates_settings_module(app, monkeypatch):
    """Regression guard for the bug class this refactor fixes: live numbers live on
    the LiveConfig snapshot, never on the settings module itself."""
    monkeypatch.setattr(app.live_config, "DocumentQA", _FakeDocumentQA)
    monkeypatch.setattr(app.live_config.config_sheet, "load", lambda *a, **k: _FAKE_FAQS)
    monkeypatch.setattr(app.live_config.config_sheet, "refresh_numbers", lambda *a, **k: {})
    monkeypatch.setattr(app.live_config.config_sheet, "save_cache", lambda *a, **k: None)
    fake_cache = {key: "+19995550100" for key in app.live_config._NUMBER_MAPPING.values()}
    monkeypatch.setattr(app.live_config.config_sheet, "load_numbers", lambda: fake_cache)
    # Do NOT mock apply_numbers here — let the real function run so this test is meaningful.

    before = {attr: getattr(app.settings, attr) for attr in app.live_config._NUMBER_MAPPING}
    config = app.live_config._build(require_sheet=False)
    after = {attr: getattr(app.settings, attr) for attr in app.live_config._NUMBER_MAPPING}

    assert after == before, "settings.py's module attributes must never be mutated by _build()"
    assert all(v == "+19995550100" for v in config.numbers.values())
