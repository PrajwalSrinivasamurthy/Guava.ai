from kb_service.ratelimit import RateLimiter


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_requests_over_the_limit_are_refused():
    limiter = RateLimiter(2, 60, clock=_Clock())

    assert [limiter.allow() for _ in range(3)] == [True, True, False]


def test_capacity_returns_as_the_window_slides():
    clock = _Clock()
    limiter = RateLimiter(2, 60, clock=clock)
    limiter.allow()
    clock.now += 30
    limiter.allow()

    assert limiter.allow() is False
    clock.now += 31
    assert limiter.allow() is True
    assert limiter.allow() is False
