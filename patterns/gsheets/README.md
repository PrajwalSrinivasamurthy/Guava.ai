# gsheets

Reusable Google Sheets read/write utilities. Supports two credential modes — **OAuth2 user credentials** (browser-based consent, cached `token.pickle`) and **Service Account** credentials (JWT-based, no consent flow). Mode is auto-detected from the credentials JSON's `type` field. Provides a small set of functions covering the common read/write/update operations.

## Adding to a project

In the project's `pyproject.toml`:

```toml
dependencies = [
    "gsheets @ file:///../../../patterns/gsheets",
    # adjust the relative path to patterns/gsheets from your project folder
]
```

Then run `uv sync`.

## Credentials setup (once per project)

Pick **one** of the two modes:

### Service Account (recommended for servers / cloud deploys)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Google Sheets API**
3. **IAM & Admin** → **Service Accounts** → **Create Service Account** → skip the optional role/user grants
4. Open the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON**. A JSON file downloads — rename to `credentials.json` and place in your project folder.
5. Copy the service account email from the **Details** tab (looks like `name@project-id.iam.gserviceaccount.com`).
6. Open the target Google Sheet → **Share** → paste the service account email → **Editor** (or Viewer if read-only) → uncheck "notify" → **Send**.
7. Add `credentials.json` to your `.gitignore`. No `token.pickle` is created in this mode.

Verify with `uv run python -m gsheets.auth` — the CLI detects SA mode, loads the key, prints the client email, and exits 0 without running an OAuth flow.

### OAuth (Desktop app, for interactive / local-dev use)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Google Sheets API**
3. Create **OAuth 2.0 credentials** (Desktop app)
4. Download the JSON and save it as `credentials.json` in your project folder
5. Add `credentials.json` and `token.pickle` to your `.gitignore`
6. Run the auth setup once:
   ```bash
   python -m gsheets.auth
   ```
   A browser window will open. After authorizing, the token is cached in `token.pickle` and subsequent runs are silent.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `GSHEETS_CREDENTIALS_FILE` | `./credentials.json` | Path to the credentials JSON (SA or OAuth) |
| `GSHEETS_TOKEN_FILE` | `./token.pickle` | OAuth-mode only — path where the token is cached. Ignored in SA mode. |

Set these in your project's `.env` if your credentials live somewhere other than the project root.

## Usage

```python
from gsheets import read_sheet, add_rows, find_row_by_value, update_row, update_row_columns

SPREADSHEET_ID = "your-spreadsheet-id-from-url"

# Read a range
rows = read_sheet(SPREADSHEET_ID, "Sheet1!A1:D10")

# Append rows
add_rows(SPREADSHEET_ID, "Sheet1!A:D", [
    ["Alice", "Smith", "alice@example.com"],
    ["Bob",   "Jones", "bob@example.com"],
])

# Find a row by value in a column (0-based column index)
result = find_row_by_value(SPREADSHEET_ID, "Sheet1!A:Z", column_index=0, value="Alice")
if result:
    row_number, row_data = result

# Overwrite an entire row
update_row(SPREADSHEET_ID, "Sheet1", row_number=2, values=["Alice", "Smith", "new@example.com"])

# Update specific columns only
update_row_columns(SPREADSHEET_ID, "Sheet1", row_number=2, column_updates={
    2: "updated@example.com",   # by 0-based index
    "D": "some other value",    # by column letter
})
```

## .env.example template

```
GSHEETS_CREDENTIALS_FILE=./credentials.json
GSHEETS_TOKEN_FILE=./token.pickle
```

## Testing-mode OAuth (7-day refresh-token expiry)

> Applies only to OAuth mode. Service accounts don't have refresh-token expiry on this cadence.


If your Google Cloud OAuth consent screen is in **Testing** publishing status, refresh tokens expire after 7 days. The auth module supports a `--testing` flag that stamps an issued-at sidecar so consumer code can warn before expiry:

```bash
# Force-deletes any existing token.pickle, runs fresh consent, stamps a
# token.pickle.issued_at sidecar.
uv run python -m gsheets.auth --testing
```

Consumer code reads the stamp via `gsheets.get_token_issued_at()`. Pair it with the `chat_notify` pattern for one-shot proactive alerts:

```python
import gsheets
from chat_notify import check_token_age

check_token_age(
    gsheets.get_token_issued_at(),
    refresh_instruction="Run `uv run python -m gsheets.auth --testing` on the host to re-auth.",
    project_name=settings.PROJECT_NAME,
)
```

### Promoting Testing → Production OAuth

When the consent screen flips to Production status, refresh tokens are effectively indefinite (only invalidated by user action or 6-months-unused). Re-run the auth command **without** `--testing`:

```bash
uv run python -m gsheets.auth
```

This deletes any stale `token.pickle.issued_at` sidecar. Easy to miss — without this step, consumer projects watching token age will keep firing proactive expiry alerts even though prod tokens never expire on that cadence. Reactive failure alerts (sheet-load errors) are unaffected either way.

## Deploy snapshots — path-deps gotcha

When using `scripts/prepare-deploy.sh` to build a `<project>/deploy/` snapshot, declare any path-sourced pattern under `[tool.uv.sources]` as **editable** so source edits propagate during dev:

```toml
[tool.uv.sources]
gsheets = { path = "../../../../patterns/gsheets", editable = true }
```

Without `editable = true`, `uv` snapshots the package at install time and your pattern edits won't surface. The deploy script auto-vendors `path`-sourced patterns into the deploy bundle by reading each pattern's own `pyproject.toml` to inline its declared deps.

## Writing phone numbers: `USER_ENTERED` silently eats the `+`

`add_rows` and `update_row*` write with `valueInputOption="USER_ENTERED"`, which is what makes
a typed `TRUE` land as a boolean and `2026-08-26` as a date. It also means Sheets parses a
leading `+` as the start of a **formula**, so `+18009332566` is stored as `18009332566`.

No error, no warning. The write reports success, the cell looks almost right, and the number
is no longer E.164 — so whatever dials it fails later, somewhere else, for a reason that does
not mention the sheet. Observed 2026-08-26 writing a config row: two phone columns lost their
`+` while the hand-typed rows beside them kept theirs.

Write phone numbers (and anything else where a leading `+`, `-`, `=` or `@` is data rather
than syntax) with **`RAW`**:

```python
service.spreadsheets().values().batchUpdate(
    spreadsheetId=sheet_id,
    body={"valueInputOption": "RAW",
          "data": [{"range": "Centers!G12", "values": [["+19253601927"]]}]},
).execute()
```

Then read it back and assert it still starts with `+`. The failure is invisible at write time,
so the only cheap place to catch it is immediately after.

## Appending a column: the grid is not infinite

A tab has a fixed `gridProperties.columnCount`. Writing one column past it fails with
`Range (Centers!J1) exceeds grid limits. Max rows: 11, max columns: 9` rather than growing the
sheet — appending *rows* auto-expands, appending *columns* does not. Add the column first:

```python
service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body={"requests": [
    {"appendDimension": {"sheetId": gid, "dimension": "COLUMNS", "length": 1}}]}).execute()
```

`gid` is `sheets[i].properties.sheetId` from `spreadsheets().get()`, not the tab's index.
