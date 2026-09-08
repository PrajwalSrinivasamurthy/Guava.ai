# inbound-online

Texas Tech Online's front-door dispatcher. Greets the caller, classifies which program
they need (Online / Graduate / K-12 / 10K Degree Completion / unsure), offers a choice
between continuing with the virtual assistant or being transferred to a live team
member, then hands off accordingly — matching legacy Grace's "Initial Bot"/"AH bot"
behavior.

## Setup

```bash
cp .env.example .env   # fill in GUAVA_AGENT_NUMBER, GUAVA_LOCAL_API_KEY
uv sync
```

FAQ content (`on_question`) loads from a Google Sheet via `config_sheet.py` — see
`.env.example` for `FAQ_SPREADSHEET_ID`/`FAQ_SHEET_TAB`. Falls back to the committed
`config_cache.json` seed if unset.

Refresh the committed seed cache from the live sheet:

```bash
uv run --env-file .env python config_sheet.py
```

## Running

```bash
uv run --env-file .env python __main__.py
```

Force business-hours state instead of the real clock (test only — not the production
mechanism):

```bash
HOURS=open uv run --env-file .env python __main__.py
HOURS=after uv run --env-file .env python __main__.py
```

## Tests

```bash
uv run --env-file .env python -m pytest tests/ -q
```

Live, scripted turn-by-turn tests against the real Dialog Engine (`tests/test_scripted.py`)
are skipped by default. Run them with a real `GUAVA_LOCAL_API_KEY`:

```bash
RUN_LIVE=1 uv run --env-file .env python -m pytest tests/test_scripted.py -v
```

## Deploy

Build the `deploy/` snapshot this project ships from (run from the repo root):

```bash
./scripts/prepare-deploy.sh customers/texas_tech/implementations/inbound-online
```

Re-run it any time before `guava deploy up` — it's idempotent and regenerates
`deploy/` from scratch each time (preserving only `guava.toml`/`.guava`).

If it fails with `Failed to initialize cache at ~/.cache/uv` (seen when running from a
sandboxed shell, e.g. Claude Code — the sandbox denies writes outside allow-listed
dirs), point uv at a writable cache instead:

```bash
UV_CACHE_DIR="$TMPDIR/uv-cache" ./scripts/prepare-deploy.sh customers/texas_tech/implementations/inbound-online
```
