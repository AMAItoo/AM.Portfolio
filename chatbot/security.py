"""Security hardening: per-IP rate limiting and input guards.

In-memory implementations are fine for a single free-tier Space process;
a restart simply resets the counters (no persistent state needed).
"""
import time
from collections import defaultdict


class RateLimiter:
    """Fixed-window per-IP limiter. `allow(ip)` -> True if under the cap."""

    def __init__(self, limit: int = 20, per_seconds: int = 60):
        self.limit = limit
        self.per_seconds = per_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        window = self._hits[ip]
        window = [t for t in window if now - t < self.per_seconds]
        self._hits[ip] = window
        if len(window) >= self.limit:
            return False
        window.append(now)
        return True

    def remaining(self, ip: str) -> int:
        now = time.monotonic()
        window = [t for t in self._hits.get(ip, []) if now - t < self.per_seconds]
        return max(0, self.limit - len(window))


MAX_INPUT_LENGTH = 1000
MAX_SESSION_TURNS = 40
SESSION_TTL_SECONDS = 2 * 60 * 60  # 2h


def sanitize_input(text: str) -> str:
    """Trim and cap the input length; strip control characters."""
    clean = "".join(ch for ch in text if ch not in "\x00\x01\x02\x03")
    return clean.strip()[:MAX_INPUT_LENGTH]