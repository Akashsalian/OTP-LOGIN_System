import time
from collections import defaultdict, deque
from threading import Lock
from .errors import AppError

def _now() -> float:
    return time.monotonic()

class SlidingWindowLimiter:
    """In-memory limiter suitable for a single-process demo; use Redis in production."""
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def check(self, action: str, key: str, rule: tuple[int, int]) -> None:
        limit, window = rule
        now = _now()
        bucket_key = (action, key)
        with self._lock:
            events = self._events[bucket_key]
            while events and now - events[0] >= window:
                events.popleft()
            if len(events) >= limit:
                retry = max(1, int(window - (now - events[0])))
                raise AppError(429, "rate_limited", "Too many requests. Please try again shortly.", retry)
            events.append(now)

    def reset(self):
        with self._lock:
            self._events.clear()

cooldowns = SlidingWindowLimiter()
requests_limiter = SlidingWindowLimiter()
