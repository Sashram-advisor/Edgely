"""T4: the per-learner sliding-window limiter (app/core/rate_limit.py).

A fake clock makes every test instant and deterministic: no sleeping.
"""

from __future__ import annotations

from app.core.rate_limit import InMemoryRateLimiter, Window


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _limiter(clock: FakeClock, per_minute: int = 3, per_day: int = 0) -> InMemoryRateLimiter:
    return InMemoryRateLimiter([Window(per_minute, 60), Window(per_day, 86_400)], clock=clock)


def test_allows_up_to_the_limit_then_rejects() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=3)
    assert [limiter.check(7).allowed for _ in range(3)] == [True, True, True]
    assert limiter.check(7).allowed is False


def test_retry_after_is_when_the_oldest_hit_leaves_the_window() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=2)
    limiter.check(7)              # t = 0
    clock.advance(10)
    limiter.check(7)              # t = 10
    clock.advance(5)              # t = 15
    decision = limiter.check(7)
    assert decision.allowed is False
    # The hit at t=0 leaves the 60 s window at t=60, i.e. 45 s from now.
    assert decision.retry_after_seconds == 45


def test_waiting_retry_after_seconds_is_enough() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=1)
    limiter.check(7)
    clock.advance(0.4)
    decision = limiter.check(7)
    assert decision.allowed is False
    clock.advance(decision.retry_after_seconds)
    assert limiter.check(7).allowed is True


def test_rejected_requests_are_not_counted() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=1)
    limiter.check(7)
    # A client hammering the endpoint must not push its own wait further out.
    for _ in range(50):
        clock.advance(1)
        limiter.check(7)
    clock.advance(10)  # 60 s after the only accepted hit
    assert limiter.check(7).allowed is True


def test_users_are_limited_independently() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=1)
    assert limiter.check(7).allowed is True
    assert limiter.check(7).allowed is False
    assert limiter.check(8).allowed is True


def test_daily_window_applies_after_the_minute_window_resets() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=10, per_day=3)
    for _ in range(3):
        assert limiter.check(7).allowed is True
        clock.advance(61)  # always outside the minute window
    decision = limiter.check(7)
    assert decision.allowed is False
    # First hit was 183 s ago; it leaves the 24 h window in 86400 - 183 s.
    assert decision.retry_after_seconds == 86_400 - 183


def test_zero_disables_a_window() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=0, per_day=0)
    assert limiter.enabled is False
    assert all(limiter.check(7).allowed for _ in range(1000))


def test_reset_forgets_everything() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, per_minute=1)
    limiter.check(7)
    limiter.reset()
    assert limiter.check(7).allowed is True
