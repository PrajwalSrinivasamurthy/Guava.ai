"""A limit on how many requests the service accepts, so a leaked key or a runaway caller
can't run up the OpenAI bill."""

import threading
import time
from collections import deque
from typing import Callable


class RateLimiter:
    """Allows at most max_requests in any window_seconds. Kept in memory, so it applies
    per running instance, which is enough for a single service."""

    def __init__(
        self, max_requests: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ):
        self.window_seconds = window_seconds
        self._max_requests = max_requests
        self._clock = clock
        self._recent: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = self._clock()
            while self._recent and now - self._recent[0] >= self.window_seconds:
                self._recent.popleft()
            if len(self._recent) >= self._max_requests:
                return False
            self._recent.append(now)
            return True
