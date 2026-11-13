"""
Client for the knowledge-base service (kb-service) that answers caller questions.

Primary API:
    KbClient(base_url, api_key, timeout_seconds).ask(question) -> KbAnswer
        Sends the question and returns KbAnswer(found, text). Raises KbUnavailable on
        any failure (timeout, network error, bad status, malformed reply) so the caller
        has one thing to catch and can fall back to a fixed message.

Question text is never included in exceptions or logs from this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

__all__ = ["KbAnswer", "KbClient", "KbUnavailable"]


class KbUnavailable(Exception):
    """The service could not answer. The message says why, never what was asked."""


@dataclass(frozen=True)
class KbAnswer:
    found: bool
    text: str = ""


class KbClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 8.0,
        max_question_chars: int = 500,
        session: requests.Session | None = None,
    ):
        """max_question_chars should match the service's limit; longer questions are cut
        rather than rejected. The session is reused so repeat questions on a call skip the
        TLS handshake."""
        self._url = base_url.rstrip("/") + "/answer"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout_seconds
        self._max_question_chars = max_question_chars
        self._session = session or requests.Session()

    def ask(self, question: str) -> KbAnswer:
        try:
            response = self._session.post(
                self._url,
                json={"question": question[: self._max_question_chars]},
                headers=self._headers,
                timeout=self._timeout,
            )
        except requests.RequestException as error:
            raise KbUnavailable(type(error).__name__) from None

        if response.status_code != 200:
            raise KbUnavailable(f"status {response.status_code}")
        try:
            body = response.json()
            found, text = bool(body["found"]), str(body["text"])
        except (ValueError, KeyError, TypeError):
            raise KbUnavailable("malformed response") from None
        return KbAnswer(found=found and bool(text), text=text)
