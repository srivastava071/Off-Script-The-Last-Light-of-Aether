import time


class TokenBucket:
    """Allows ``rate`` requests per second on average, with bursts up to ``capacity``."""

    def __init__(self, rate: float, capacity: int, clock=time.monotonic):
        self.rate = rate
        self.capacity = capacity
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def allow(self) -> bool:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False
