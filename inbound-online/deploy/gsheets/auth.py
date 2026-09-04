"""
Google Sheets API authentication — supports both OAuth user credentials
(Desktop-app installed flow with a cached token) and Service Account
credentials (JWT-based, no consent flow, no token cache).

Mode is auto-detected from the credentials JSON's `type` field:
  - `service_account`  → SA path: no token cache, no interactive consent.
  - anything else       → OAuth path: browser consent on first run,
                          token.pickle for subsequent runs.

Credentials and token paths are configured via environment variables:
  GSHEETS_CREDENTIALS_FILE  — path to credentials JSON
                               (default: ./credentials.json in the current working directory)
  GSHEETS_TOKEN_FILE        — OAuth-only: path where the token is cached after first login
                               (default: ./token.pickle). Ignored in SA mode.

Run this file directly to set up OAuth authentication for a project:
    python -m gsheets.auth               # production OAuth app
    python -m gsheets.auth --testing     # Testing-status OAuth app (7-day refresh token)

For SA mode this CLI just verifies the key file and prints the SA email to
share the sheet with — there's no consent flow to run.

The --testing flag stamps a sidecar file (token.pickle.issued_at) so callers
can proactively warn before the 7-day refresh token expires. Production runs
delete any stale sidecar so promotion from Testing → Production is clean.

Prerequisites:
1. Go to Google Cloud Console (console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the Google Sheets API
4. Either:
   - Create OAuth 2.0 credentials (Desktop app) and download the JSON, OR
   - Create a Service Account, generate a JSON key, and share the target
     spreadsheet with the service account email.
5. Save the JSON at GSHEETS_CREDENTIALS_FILE.
"""

import argparse
import json
import os
import pickle
import webbrowser
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

_CREDENTIALS_FILE = os.environ.get("GSHEETS_CREDENTIALS_FILE", "credentials.json")
_TOKEN_FILE       = os.environ.get("GSHEETS_TOKEN_FILE",       "token.pickle")
_ISSUED_AT_FILE   = _TOKEN_FILE + ".issued_at"


def _is_service_account_credentials_file(path: str) -> bool:
    """Return True if the JSON at `path` is a Service Account key."""
    try:
        with open(path) as f:
            return json.load(f).get("type") == "service_account"
    except (OSError, ValueError):
        return False


def get_credentials():
    """
    Return valid credentials. In SA mode, builds JWT-based credentials from
    the service-account JSON — no token cache, no consent flow. In OAuth
    mode, reads/refreshes/caches token.pickle and runs the installed-app
    consent flow when there's no valid cached token.
    """
    if not os.path.exists(_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Credentials file not found: {_CREDENTIALS_FILE!r}\n"
            "Set GSHEETS_CREDENTIALS_FILE or place credentials.json in the current directory.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials."
        )

    if _is_service_account_credentials_file(_CREDENTIALS_FILE):
        return ServiceAccountCredentials.from_service_account_file(
            _CREDENTIALS_FILE, scopes=SCOPES,
        )

    creds = None

    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_FILE, SCOPES)
            try:
                webbrowser.get()
                open_browser = True
            except webbrowser.Error:
                print("No launchable browser found — copy the URL below into any browser to authorize.")
                open_browser = False
            creds = flow.run_local_server(port=0, open_browser=open_browser)

        with open(_TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)

    return creds


def get_sheets_service():
    """Build and return the Google Sheets API service."""
    return build('sheets', 'v4', credentials=get_credentials())


def get_token_issued_at() -> datetime | None:
    """Return the UTC datetime when the current token was issued, or None if no
    sidecar exists. The sidecar is written by `python -m gsheets.auth --testing`
    to enable proactive expiry warnings for 7-day Testing-status OAuth tokens.
    Production tokens never have the sidecar, so this returns None and callers
    treat the token as indefinitely valid."""
    if not os.path.exists(_ISSUED_AT_FILE):
        return None
    try:
        with open(_ISSUED_AT_FILE) as f:
            return datetime.fromisoformat(f.read().strip())
    except Exception:
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set up Google Sheets authentication for this project.",
    )
    parser.add_argument(
        "--testing",
        action="store_true",
        help=(
            "OAuth-only: mark this token as issued under a Testing-status "
            "OAuth app. Forces a fresh consent flow and stamps a sidecar "
            "file so the calling app can warn before the 7-day refresh "
            "token expires. Omit for Production-status OAuth apps — any "
            "existing sidecar will be removed. Ignored in service-account "
            "mode."
        ),
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Google Sheets API — Authentication Setup")
    print("=" * 60)
    print()
    print(f"Credentials file : {_CREDENTIALS_FILE}")

    if not os.path.exists(_CREDENTIALS_FILE):
        print()
        print(f"ERROR: credentials file not found at {_CREDENTIALS_FILE!r}")
        print()
        print("Steps:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. Enable the Google Sheets API")
        print("  3. Either:")
        print("     - Create OAuth 2.0 credentials (Desktop app), or")
        print("     - Create a Service Account and generate a JSON key")
        print("  4. Download the JSON and save it at the path above")
        print("     (or set GSHEETS_CREDENTIALS_FILE to point elsewhere)")
        exit(1)

    if _is_service_account_credentials_file(_CREDENTIALS_FILE):
        with open(_CREDENTIALS_FILE) as f:
            sa_email = json.load(f).get("client_email", "<unknown>")
        print("Mode             : service account")
        print(f"Client email     : {sa_email}")
        print()
        try:
            get_sheets_service()
        except Exception as e:
            print(f"Service account credentials failed to load: {e}")
            exit(1)
        print(
            "Service account credentials loaded — no auth flow needed.\n"
            "Make sure the target spreadsheet is shared with the client "
            "email above (Editor for read/write, Viewer for read-only)."
        )
        exit(0)

    mode_label = "testing (7-day expiry warning enabled)" if args.testing else "production"
    print(f"Token cache file : {_TOKEN_FILE}")
    print(f"Mode             : {mode_label}")
    print()

    # --testing forces fresh consent so the stamp accurately reflects issue time.
    if args.testing and os.path.exists(_TOKEN_FILE):
        os.remove(_TOKEN_FILE)
        print(f"Removed existing token at {_TOKEN_FILE!r} to force fresh consent.")

    print("Starting OAuth flow — a browser window will open...")
    print()
    try:
        get_credentials()
        get_sheets_service()
    except Exception as e:
        print(f"Authentication failed: {e}")
        exit(1)

    if args.testing:
        with open(_ISSUED_AT_FILE, 'w') as f:
            f.write(datetime.now(timezone.utc).isoformat())
        print(f"Authentication successful. Token cached at {_TOKEN_FILE!r}")
        print(f"Stamped {_ISSUED_AT_FILE!r} — proactive 6-day expiry warning is enabled.")
    else:
        if os.path.exists(_ISSUED_AT_FILE):
            os.remove(_ISSUED_AT_FILE)
            print(f"Removed stale {_ISSUED_AT_FILE!r} (production mode).")
        print(f"Authentication successful. Token cached at {_TOKEN_FILE!r}")
