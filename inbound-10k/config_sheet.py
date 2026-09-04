"""
Loads Texas Tech 10K Degree Completion Program FAQ content from a Google Sheet.

Expected sheet structure — this program's tab (settings.FAQ_SHEET_TAB, default "10K
FAQs"), three columns, header row skipped:
      category | question | answer

Other Texas Tech programs' FAQ content lives in separate tabs of the same spreadsheet
(e.g. "Online FAQs", "Grad FAQs", "K12 FAQs") rather than mixed into one tab with a
program column — each program's own project reads only its own tab. Note: legacy
Grace's 10K bot has its own attached knowledge base ("10K Degree Completion Program AH
(PRD)"), but we don't have that KB's actual content, so this is freshly authored
content, not a replication of it.

On every successful load, a local cache is written to /tmp so the deployed project
directory can stay read-only. There is no committed seed yet (no content existed for
this program prior to a real Sheet) — until one is set up, load() falls back to
raising, which __main__.py catches and degrades to a fixed fallback message.

If the sheet is unreachable, the cache is used as a fallback and a warning is logged.

Run this module directly to refresh the committed seed (project dir + deploy/) from the
live sheet — reuses save_cache() so the seed can't drift from the runtime cache format:

    uv run --env-file .env python config_sheet.py
"""

import json
import logging
import os
from datetime import datetime

import gsheets

import settings

logger = logging.getLogger(__name__)

# Runtime writes go to /tmp because the deployed project dir is read-only on Guava
# Cloud. The committed seed (same filename, in the project dir) ships with the deploy
# bundle and is used only as a read fallback when /tmp is empty.
_RUNTIME_CACHE_PATH = "/tmp/inbound_10k_faq_cache.json"
_SEED_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_cache.json")

# Shared phone-number config tab — same spreadsheet as the FAQ content above, but one
# tab shared by all 4 Texas Tech programs rather than per-program.
_NUMBER_SHEET_TAB = "Shared Config"


def load(spreadsheet_id: str, require_sheet: bool = False) -> list[dict]:
    """
    Load the FAQs tab from the Google Sheet.
    Saves a local cache on success; falls back to the cache on any error
    (unless require_sheet is True).

    Returns a list of {category, question, answer} dicts.
    """
    if not spreadsheet_id:
        if require_sheet:
            raise RuntimeError(
                "FAQ_SPREADSHEET_ID is not set and require_sheet=True. "
                "Set FAQ_SPREADSHEET_ID or pass require_sheet=False to allow cache fallback."
            )
        logger.info("No FAQ_SPREADSHEET_ID set — loading from local cache.")
        return _load_cache()

    try:
        faqs = _load_faqs(spreadsheet_id)
        save_cache(faqs=faqs)
        return faqs
    except Exception as e:
        if require_sheet:
            raise
        logger.warning(
            "Failed to load FAQs from Google Sheet (%s). Verify the service account "
            "has Editor access to the spreadsheet and the Google Sheets API is enabled. "
            "Falling back to local cache (runtime %r, seed %r).",
            e, _RUNTIME_CACHE_PATH, _SEED_CACHE_PATH,
        )
        return _load_cache()


def _load_faqs(spreadsheet_id: str) -> list[dict]:
    rows = gsheets.read_sheet(spreadsheet_id, f"{settings.FAQ_SHEET_TAB}!A:C")
    if not rows:
        raise RuntimeError(f"Could not read {settings.FAQ_SHEET_TAB!r} tab")

    faqs = []
    for row in rows[1:]:  # skip header
        while len(row) < 3:
            row.append("")
        category, question, answer = row[0].strip(), row[1].strip(), row[2].strip()
        if not question or not answer:
            continue
        faqs.append({"category": category or settings.ORGANIZATION_NAME, "question": question, "answer": answer})
    return faqs


def render_corpus(faqs: list[dict]) -> str:
    """Render FAQs grouped by category into the text blob DocumentQA ingests."""
    by_category: dict[str, list[dict]] = {}
    for faq in faqs:
        by_category.setdefault(faq["category"], []).append(faq)

    lines: list[str] = []
    for category, items in by_category.items():
        lines.append(f"# {category}")
        lines.append("")
        for faq in items:
            lines.append(f"Q: {faq['question']}")
            lines.append(f"A: {faq['answer']}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def load_numbers() -> dict[str, str]:
    """Read the cached "Shared Config" phone numbers — NEVER touches the network.

    Numbers are refreshed at deploy time (`uv run --env-file .env python
    config_sheet.py`, wired into scripts/prepare-deploy.sh), not on every process
    start, so a transient Sheets outage can never block the agent from starting.
    Returns {} if nothing has been cached yet (fresh checkout, never refreshed) —
    apply_numbers() below falls back to settings.py's hardcoded defaults in that case.
    """
    for path, source in ((_RUNTIME_CACHE_PATH, "runtime"), (_SEED_CACHE_PATH, "bundled seed")):
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        numbers = data.get("numbers") or {}
        if numbers:
            logger.info("Using cached numbers from %s [%s] (saved at %s).",
                        path, source, data.get("saved_at", "unknown"))
            return numbers
    return {}


def apply_numbers(target, mapping: dict[str, str]) -> None:
    """Override `target` module's number constants from the cached "Shared Config"
    values. `mapping` is {settings attr name: sheet key}, e.g.
    {"LIVE_NUMBER": "tenk_live"}. An explicit env var for that attr always wins.

    Never touches the network and never raises — a key missing from the cache (not
    yet refreshed, or genuinely absent from the sheet) just leaves `target`'s existing
    hardcoded default in place.
    """
    numbers = load_numbers()
    for attr, key in mapping.items():
        if attr not in os.environ and key in numbers:
            setattr(target, attr, numbers[key])


def refresh_numbers(spreadsheet_id: str) -> dict[str, str]:
    """Pull the live "Shared Config" tab: key | number columns, header row skipped.

    This is the ONLY function that hits the network for numbers — call it at deploy
    time (see the CLI block below / scripts/prepare-deploy.sh), never at agent
    startup. Raises on any read failure or an unset spreadsheet_id: a broken refresh
    should be visible to whoever's building the deploy, not silently shipped with
    stale numbers.
    """
    if not spreadsheet_id:
        raise RuntimeError(
            "FAQ_SPREADSHEET_ID is not set — cannot refresh numbers from a sheet "
            "that isn't configured."
        )
    rows = gsheets.read_sheet(spreadsheet_id, f"{_NUMBER_SHEET_TAB}!A:B")
    if not rows:
        raise RuntimeError(f"Could not read {_NUMBER_SHEET_TAB!r} tab (empty response)")

    numbers: dict[str, str] = {}
    for row in rows[1:]:  # skip header
        if len(row) < 2:
            continue
        key, number = row[0].strip(), row[1].strip()
        if not key or not number:
            continue
        # Sheets parses a leading "+" as a formula and drops it on write — defend
        # on read too.
        if not number.startswith("+"):
            number = "+" + number
        numbers[key] = number
    return numbers


def save_cache(path: str = _RUNTIME_CACHE_PATH, *, faqs: list[dict] | None = None,
               numbers: dict[str, str] | None = None) -> None:
    """Persist a fresh snapshot, MERGING into whatever's already cached at `path` so
    refreshing one section (faqs or numbers) never wipes the other. Defaults to the
    runtime cache (/tmp); pass `path` to write the committed seed instead (used by the
    __main__ refresh CLI below). Failures are logged but never raised; write is
    best-effort."""
    existing: dict = {}
    try:
        if os.path.exists(path):
            with open(path) as f:
                existing = json.load(f)
    except Exception:
        existing = {}
    if faqs is not None:
        existing["faqs"] = faqs
    if numbers is not None:
        existing["numbers"] = numbers
    existing["saved_at"] = datetime.now().isoformat()
    try:
        with open(path, "w") as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.warning("Could not write cache to %r: %s", path, e)


def _load_cache() -> list[dict]:
    if os.path.exists(_RUNTIME_CACHE_PATH):
        path, source = _RUNTIME_CACHE_PATH, "runtime"
    elif os.path.exists(_SEED_CACHE_PATH):
        path, source = _SEED_CACHE_PATH, "bundled seed"
    else:
        raise RuntimeError(
            "Google Sheet is unreachable and no local FAQ cache exists. "
            "Place a valid service-account credentials.json in the project dir and "
            "share the spreadsheet with the service account email, or run "
            "config_sheet.py once with a live sheet to seed the cache."
        )
    with open(path) as f:
        data = json.load(f)
    logger.warning(
        "Using cached FAQs from %s [%s] (saved at %s).",
        path, source, data.get("saved_at", "unknown"),
    )
    return data["faqs"]


# ── Seed-cache refresh CLI ───────────────────────────────────────────────────
# Refresh the committed seed cache (FAQs + shared phone-number config) from the live
# sheet — this is what scripts/prepare-deploy.sh runs automatically before every
# deploy, so numbers only ever change on a deploy, never mid-process:
#     uv run --env-file .env python config_sheet.py
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if not settings.FAQ_SPREADSHEET_ID:
        raise SystemExit(
            "FAQ_SPREADSHEET_ID not set — set it in .env before refreshing the seed cache."
        )

    _faqs = load(settings.FAQ_SPREADSHEET_ID, require_sheet=True)
    _numbers = refresh_numbers(settings.FAQ_SPREADSHEET_ID)

    _here = os.path.dirname(os.path.abspath(__file__))
    _targets = [
        os.path.join(_here, "config_cache.json"),
        os.path.join(_here, "deploy", "config_cache.json"),
    ]
    for _target in _targets:
        if not os.path.isdir(os.path.dirname(_target)):
            logger.info("Skipping %s — directory not present.", _target)
            continue
        save_cache(path=_target, faqs=_faqs, numbers=_numbers)
        logger.info("Refreshed seed cache: %s", _target)

    logger.info("Done — %d FAQs, %d numbers loaded.", len(_faqs), len(_numbers))
