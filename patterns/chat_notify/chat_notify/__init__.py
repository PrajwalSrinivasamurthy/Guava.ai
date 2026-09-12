"""
Thin Google Chat webhook notifier + helpers that build on it.

Primary API:
    notify(message, project_name=None)
        Post a message to GOOGLE_CHAT_WEBHOOK_URL. Prefixes with a project
        name so a shared Space can host alerts from multiple projects.
        No-op if the webhook URL isn't configured. Network errors are
        swallowed (logged) so notification failure never breaks the caller.

Specialized helper:
    check_token_age(issued_at, refresh_instruction, ...)
        One-shot alert when a token is close to expiry. Caller passes the
        issued-at timestamp (from wherever) and the command a human should
        run to re-auth — this module stays agnostic about which token.

Env vars read:
    GOOGLE_CHAT_WEBHOOK_URL — incoming webhook for the Chat Space. Treat as
                              secret. If unset, notify() is a no-op.
    PROJECT_NAME            — prefixed to messages as [PROJECT_NAME]. If
                              unset, messages are sent without a prefix.
                              Either env var or the project_name argument
                              to notify() may supply this; the argument wins.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

__all__ = ["notify", "check_token_age"]


def notify(message: str, project_name: Optional[str] = None) -> None:
    """Post `message` to GOOGLE_CHAT_WEBHOOK_URL, prefixed with a project
    name for disambiguation in a shared Space.

    Args:
        message: The text to send.
        project_name: Prefix for the message. Defaults to the PROJECT_NAME
                      env var; if neither is set, the message is sent
                      without a prefix.

    Failure modes are silent-by-design: no webhook configured → no-op;
    HTTP or network error → warning logged, no exception raised.
    """
    webhook_url = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", "")
    if not webhook_url:
        return

    name = project_name if project_name is not None else os.environ.get("PROJECT_NAME", "")
    text = f"[{name}] {message}" if name else message

    try:
        requests.post(webhook_url, json={"text": text}, timeout=5)
    except Exception as e:
        logger.warning("Failed to send Google Chat notification: %s", e)


# Dedup state — keyed by alert_id so one process can watch multiple tokens
# without them stepping on each other. Value is the issued_at we last
# alerted for; resets when a newer token is detected (fresh re-auth).
_warned_expiry_for: dict[str, datetime] = {}


def check_token_age(
    issued_at: Optional[datetime],
    refresh_instruction: str = "re-auth the token",
    project_name: Optional[str] = None,
    warn_after_days: int = 6,
    alert_id: str = "default",
) -> None:
    """Fire a one-shot Chat alert when `issued_at` is ≥ `warn_after_days` old.

    Args:
        issued_at: When the token was issued (UTC). None means "unknown /
                   no sidecar", which is silently skipped — typical of
                   Production-status OAuth tokens with no expiry tracking.
        refresh_instruction: The exact command the operator should run to
                             re-auth. Included verbatim in the alert body
                             so chat_notify stays agnostic to which token
                             system this is (gsheets OAuth, service
                             accounts, Slack bot tokens, etc.).
        project_name: Prefix for the alert. Passed through to notify().
        warn_after_days: Threshold in days. Default 6, giving ~24 hours
                         heads-up for the 7-day Google Testing-status
                         refresh-token limit.
        alert_id: Key for dedup state. Use distinct ids if one process
                  watches multiple tokens. Default is fine for a single
                  token per process.

    Behavior:
        - Below threshold → silent, clears any prior warn state for this
          alert_id (so a fresh re-auth resets the one-shot).
        - At/above threshold + not already warned for this exact
          issued_at → fires notify() once.
        - Same issued_at already warned → silent (dedup).
        - A newer issued_at (detected as a change) resets the flag so the
          next threshold crossing will fire a fresh alert.
    """
    if issued_at is None:
        return

    age = datetime.now(timezone.utc) - issued_at
    if age.days < warn_after_days:
        _warned_expiry_for.pop(alert_id, None)
        return

    if _warned_expiry_for.get(alert_id) == issued_at:
        return

    notify(
        f"OAuth token is {age.days} days old — refresh-token limit is imminent. "
        f"{refresh_instruction}",
        project_name=project_name,
    )
    _warned_expiry_for[alert_id] = issued_at
