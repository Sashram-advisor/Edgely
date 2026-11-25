"""Per-user rate limit for the tutor (T4).

Every tutor question costs real money (one or two model calls). Before T4
nothing stopped one learner, a buggy client or a stolen token from sending
thousands of questions. This module adds a per-user limit to
``POST /tutor/chat`` and ``POST /tutor/chat/stream``.

Design
------
* **Sliding window log.** For each user we keep the timestamps of their recent
  *accepted* questions. A new question is accepted when fewer than ``limit``
  timestamps fall inside each window. This is exact (no burst at the edge of a
  fixed minute) and cheap at our scale (a few hundred timestamps per user, max).
* **Two windows.** A short one (per minute) stops bursts; a long one (per day)
  caps total cost. Both are configurable in ``backend/.env``:
  ``TUTOR_RATE_LIMIT_PER_MINUTE`` and ``TUTOR_RATE_LIMIT_PER_DAY``. ``0``
  disables that window.
* **Rejected requests are not counted.** Otherwise a client that keeps retrying
  would lock itself out forever.
* **Retry-After.** A rejection returns HTTP 429 with a ``Retry-After`` header
  (whole seconds, rounded up) saying when the oldest relevant timestamp leaves
  the window, as RFC 9110 recommends.

Limitation (documented on purpose)
----------------------------------
The state lives in this process's memory. With several uvicorn workers or
several containers, each one enforces its own limit, so the effective limit is
``limit x number_of_processes``, and a restart resets the counters. That is
acceptable for the MVP (one process). Before scaling out, swap
``InMemoryRateLimiter`` for a Redis-backed class with the same ``check`` method.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.dependencies import current_user_id

# Error code returned in the X-Error-Code header so clients can tell this 429
# apart from any other 429 (documented in docs/api/tutor-sse.md).
RATE_LIMIT_ERROR_CODE = "TUTOR_RATE_LIMITED"


@dataclass(frozen=True)
class Window:
    """One limit: at most ``limit`` accepted requests per ``seconds``."""

    limit: int
    seconds: float


@dataclass(frozen=True)
class Decision:
    """Result of one ``check`` call."""

    allowed: bool
    #: Seconds until the request would be allowed. 0 when ``allowed``.
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    """Thread-safe sliding-window limiter keyed by an arbitrary hashable key.

    The tutor routes are plain ``def`` functions that FastAPI runs in a thread
    pool, so two requests from the same user can arrive at the same time. A
    single lock around the read-check-write keeps the count exact.
    """

    def __init__(self, windows: list[Window], clock: Callable[[], float] = time.monotonic) -> None:
        # Windows with limit <= 0 are switched off.
        self._windows = [w for w in windows if w.limit > 0 and w.seconds > 0]
        # The longest window decides how much history we must keep.
        self._horizon = max((w.seconds for w in self._windows), default=0.0)
        # time.monotonic is not affected by wall-clock changes (NTP, DST).
        # Tests inject a fake clock.
        self._clock = clock
        self._hits: dict[object, deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._windows)

    def check(self, key: object) -> Decision:
        """Accept and record one request for ``key``, or reject it.

        Rejected requests are *not* recorded.
        """
        if not self._windows:
            return Decision(allowed=True)

        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())

            # Forget timestamps older than the longest window.
            while hits and now - hits[0] >= self._horizon:
                hits.popleft()

            wait = 0.0
            for window in self._windows:
                # Timestamps inside this window, oldest first. `hits` is sorted
                # because we only ever append the current time.
                inside = [t for t in hits if now - t < window.seconds]
                if len(inside) >= window.limit:
                    # The request becomes allowed when enough old timestamps
                    # leave the window: the (len - limit + 1)-th oldest one.
                    oldest_blocking = inside[len(inside) - window.limit]
                    wait = max(wait, oldest_blocking + window.seconds - now)

            if wait > 0:
                # Round up so a client that waits exactly Retry-After seconds succeeds.
                return Decision(allowed=False, retry_after_seconds=max(1, math.ceil(wait)))

            hits.append(now)
            return Decision(allowed=True)

    def reset(self) -> None:
        """Forget all history (used by tests)."""
        with self._lock:
            self._hits.clear()


def _build_tutor_limiter() -> InMemoryRateLimiter:
    """Create the tutor limiter from settings (see backend/.env.example)."""
    return InMemoryRateLimiter(
        [
            Window(limit=settings.tutor_rate_limit_per_minute, seconds=60),
            Window(limit=settings.tutor_rate_limit_per_day, seconds=24 * 60 * 60),
        ]
    )


# One shared limiter for the process. Tests may call tutor_limiter.reset() or
# replace the dependency below with app.dependency_overrides.
tutor_limiter = _build_tutor_limiter()


def enforce_tutor_rate_limit(user_id: int = Depends(current_user_id)) -> int:
    """FastAPI dependency: 429 when this learner asked too many questions.

    It depends on ``current_user_id``, so the key is the verified platform user
    id from the login token, never anything the client sends. FastAPI caches
    dependencies per request, so a route that also asks for ``current_user_id``
    does not run the database lookup twice.

    Returns the user id so a route can use this dependency in place of
    ``current_user_id``.
    """
    decision = tutor_limiter.check(user_id)
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            # Same {"detail": "..."} shape as every other error in the M1 contract,
            # so frontend/utilities/api.ts shows it without changes.
            detail=f"You're asking questions faster than the tutor allows. Try again in {decision.retry_after_seconds} seconds.",
            headers={
                "Retry-After": str(decision.retry_after_seconds),
                "X-Error-Code": RATE_LIMIT_ERROR_CODE,
            },
        )
    return user_id
