"""Keeps a connection to OpenAI open between questions.

Idle connections are closed after a few seconds by default, so most questions on a call
would open a new one (a DNS lookup and a TLS handshake) in the middle of a caller's wait.
A cheap request on a timer keeps one connection warm.
"""

import logging
import threading
from typing import Callable

logger = logging.getLogger("kb_service.warmup")


class KeepWarm:
    def __init__(self, ping: Callable[[], None], interval_seconds: float):
        self._ping = ping
        self._interval = interval_seconds
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name="keep-warm", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while True:
            try:
                self._ping()
            except Exception as error:
                logger.warning("warm-up request failed: %s", type(error).__name__)
            if self._stopped.wait(self._interval):
                return
