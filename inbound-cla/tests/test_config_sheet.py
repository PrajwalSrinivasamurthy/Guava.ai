"""Direct coverage of config_sheet.py's cache fallback: the load()/_load_cache()
runtime-then-seed precedence and save_cache()'s merge behavior. test_live_config.py
monkeypatches config_sheet out entirely, so none of this is exercised anywhere else —
these tests hit the real functions, with _RUNTIME_CACHE_PATH/_SEED_CACHE_PATH
redirected into tmp_path so nothing touches the real /tmp cache or the committed seed.
"""

import json
import types

import pytest

import config_sheet

_FAQ_ROWS = [
    ["category", "question", "answer"],
    ["General", "What are your hours?", "9-5 Mon-Fri."],
]
_FAQS = [{"category": "General", "question": "What are your hours?", "answer": "9-5 Mon-Fri."}]


@pytest.fixture(autouse=True)
def _isolated_cache_paths(tmp_path, monkeypatch):
    runtime_path = str(tmp_path / "runtime_cache.json")
    monkeypatch.setattr(config_sheet, "_RUNTIME_CACHE_PATH", runtime_path)
    monkeypatch.setattr(config_sheet, "_SEED_CACHE_PATH", str(tmp_path / "seed_cache.json"))
    # save_cache()'s `path` default is bound to _RUNTIME_CACHE_PATH's value at def
    # time, so reassigning the module attr above doesn't redirect callers (like
    # load()) that rely on the default — patch the function's bound default too.
    monkeypatch.setattr(config_sheet.save_cache, "__defaults__", (runtime_path,))


def _write_cache(path, *, faqs=None, numbers=None, saved_at="2026-01-01T00:00:00"):
    data = {"saved_at": saved_at}
    if faqs is not None:
        data["faqs"] = faqs
    if numbers is not None:
        data["numbers"] = numbers
    with open(path, "w") as f:
        json.dump(data, f)


# ── load() / _load_cache() fallback ────────────────────────────────────────────

def test_load_uses_cache_when_no_spreadsheet_id(monkeypatch):
    _write_cache(config_sheet._SEED_CACHE_PATH, faqs=_FAQS)
    monkeypatch.setattr(
        config_sheet.gsheets, "read_sheet",
        lambda *a, **k: pytest.fail("must not hit the network with no spreadsheet_id"),
    )

    assert config_sheet.load("", require_sheet=False) == _FAQS


def test_load_with_no_spreadsheet_id_and_require_sheet_raises():
    with pytest.raises(RuntimeError):
        config_sheet.load("", require_sheet=True)


def test_load_falls_back_to_cache_on_sheet_error(monkeypatch):
    _write_cache(config_sheet._RUNTIME_CACHE_PATH, faqs=_FAQS)
    monkeypatch.setattr(
        config_sheet.gsheets, "read_sheet",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sheet down")),
    )

    assert config_sheet.load("sheet-id", require_sheet=False) == _FAQS


def test_load_require_sheet_propagates_sheet_error(monkeypatch):
    monkeypatch.setattr(
        config_sheet.gsheets, "read_sheet",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sheet down")),
    )

    with pytest.raises(RuntimeError):
        config_sheet.load("sheet-id", require_sheet=True)


def test_load_saves_cache_on_success(monkeypatch):
    monkeypatch.setattr(config_sheet.gsheets, "read_sheet", lambda *a, **k: _FAQ_ROWS)

    assert config_sheet.load("sheet-id", require_sheet=False) == _FAQS

    with open(config_sheet._RUNTIME_CACHE_PATH) as f:
        cached = json.load(f)
    assert cached["faqs"] == _FAQS


def test_load_cache_prefers_runtime_over_seed():
    _write_cache(config_sheet._RUNTIME_CACHE_PATH,
                 faqs=[{"category": "C", "question": "runtime", "answer": "a"}])
    _write_cache(config_sheet._SEED_CACHE_PATH,
                 faqs=[{"category": "C", "question": "seed", "answer": "a"}])

    assert config_sheet._load_cache()[0]["question"] == "runtime"


def test_load_cache_falls_back_to_seed_when_runtime_missing():
    _write_cache(config_sheet._SEED_CACHE_PATH,
                 faqs=[{"category": "C", "question": "seed", "answer": "a"}])

    assert config_sheet._load_cache()[0]["question"] == "seed"


def test_load_cache_raises_when_neither_cache_exists():
    with pytest.raises(RuntimeError):
        config_sheet._load_cache()


# ── save_cache() merge behavior ────────────────────────────────────────────────

def test_save_cache_merges_numbers_without_wiping_faqs():
    config_sheet.save_cache(faqs=_FAQS)
    config_sheet.save_cache(numbers={"shared_number": "+15550000000"})

    with open(config_sheet._RUNTIME_CACHE_PATH) as f:
        data = json.load(f)
    assert data["faqs"] == _FAQS
    assert data["numbers"] == {"shared_number": "+15550000000"}


def test_save_cache_merges_faqs_without_wiping_numbers():
    config_sheet.save_cache(numbers={"shared_number": "+15550000000"})
    config_sheet.save_cache(faqs=_FAQS)

    with open(config_sheet._RUNTIME_CACHE_PATH) as f:
        data = json.load(f)
    assert data["numbers"] == {"shared_number": "+15550000000"}
    assert data["faqs"] == _FAQS


# ── load_numbers() / apply_numbers() ───────────────────────────────────────────

def test_load_numbers_returns_empty_when_nothing_cached():
    assert config_sheet.load_numbers() == {}


def test_load_numbers_prefers_runtime_over_seed():
    _write_cache(config_sheet._RUNTIME_CACHE_PATH, numbers={"shared_number": "+1runtime"})
    _write_cache(config_sheet._SEED_CACHE_PATH, numbers={"shared_number": "+1seed"})

    assert config_sheet.load_numbers() == {"shared_number": "+1runtime"}


def test_apply_numbers_sets_attr_from_cache(monkeypatch):
    _write_cache(config_sheet._RUNTIME_CACHE_PATH, numbers={"shared_number": "+15551234567"})
    monkeypatch.delenv("LIVE_NUMBER", raising=False)
    target = types.SimpleNamespace(LIVE_NUMBER="+1default")

    config_sheet.apply_numbers(target, {"LIVE_NUMBER": "shared_number"})

    assert target.LIVE_NUMBER == "+15551234567"


def test_apply_numbers_env_var_wins_over_cache(monkeypatch):
    _write_cache(config_sheet._RUNTIME_CACHE_PATH, numbers={"shared_number": "+15551234567"})
    monkeypatch.setenv("LIVE_NUMBER", "+1envoverride")
    target = types.SimpleNamespace(LIVE_NUMBER="+1default")

    config_sheet.apply_numbers(target, {"LIVE_NUMBER": "shared_number"})

    # env var present → cache ignored, target left untouched (caller already set it from env)
    assert target.LIVE_NUMBER == "+1default"


def test_apply_numbers_leaves_default_when_key_missing_from_cache(monkeypatch):
    monkeypatch.delenv("LIVE_NUMBER", raising=False)
    _write_cache(config_sheet._RUNTIME_CACHE_PATH, numbers={})
    target = types.SimpleNamespace(LIVE_NUMBER="+1default")

    config_sheet.apply_numbers(target, {"LIVE_NUMBER": "shared_number"})

    assert target.LIVE_NUMBER == "+1default"
