"""Keeps requests at or below a requests-per-minute limit by spacing them out.

With GEMINI_RPM=5 the pacer makes sure at least 60/5 = 12 s pass between the *start* of two
requests. Simple and predictable — enough for one worker; it doesn't coordinate across processes.
"""

import time
from collections.abc import Callable


class Pacer:
    def __init__(
        self,
        requests_per_minute: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.min_interval = 60.0 / requests_per_minute
        self._clock = clock
        self._sleep = sleep
        self._last_start: float | None = None

    def wait(self) -> float:
        """Block until the next request is allowed. Returns how long it waited (seconds)."""
        now = self._clock()
        waited = 0.0
        if self._last_start is not None:
            waited = max(0.0, self._last_start + self.min_interval - now)
            if waited:
                self._sleep(waited)
        self._last_start = self._clock()
        return waited
