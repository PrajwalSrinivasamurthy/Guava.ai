"""Probabilistic-testing helpers for non-deterministic Guava behavior. See gotchas/agent-testing.md §4.

Intent routing and roleplay vary run-to-run, so score a persona over N samples and assert a
pass RATE — never fail on the first stochastic miss.
"""

from __future__ import annotations

from typing import Any, Callable


def judge_bool(
    session: Any,
    pass_criteria: list[str] | None = None,
    fail_criteria: list[str] | None = None,
) -> bool:
    """Run ``session.evaluate(...)`` (the soft LLM judge) but return True/False instead of
    raising, so a fuzzy verdict can be ONE signal among many in a sampled/aggregate test.

    Reminder (gotchas/agent-testing.md §3): the judge only sees the transcript — use it for speech
    qualities, never routing/state. Prefer it combined with a deterministic predicate.
    """
    try:
        session.evaluate(pass_criteria=pass_criteria, fail_criteria=fail_criteria)
        return True
    except AssertionError:
        return False


def pass_rate(
    session_factory: Callable[[], Any],
    predicate: Callable[[Any], bool],
    samples: int = 5,
    name: str = "",
    printer: Callable[[str], None] | None = print,
) -> tuple[int, int, float]:
    """Run ``session_factory()`` `samples` times, scoring each COMPLETED session with
    ``predicate(session) -> bool``, and return ``(passes, samples, rate)``.

    ``session_factory`` must return a *completed* session — e.g.
    ``lambda: agent.test_roleplay(persona)`` (roleplay runs to completion on return), or a
    thunk that opens ``agent.test()``, drives it, and returns the session after the block.

    Use a DETERMINISTIC ``predicate`` (an ``executed_actions`` / ``termination_reason`` /
    captured-state check) so the rate isn't doubly non-deterministic; keep the soft judge
    (via ``judge_bool``) as at most one clause. A run that raises counts as a MISS, not a
    suite abort. The observed rate is printed for CI drift visibility. The caller asserts
    ``rate >= threshold``.

    Runs SERIALLY — safe with process-global spies. Parallelize yourself only if the
    predicate touches no shared monkeypatched state.
    """
    passes = 0
    misses: list[tuple] = []
    for i in range(samples):
        try:
            session = session_factory()
            if predicate(session):
                passes += 1
            else:
                misses.append(
                    (
                        i,
                        getattr(session, "termination_reason", None),
                        list(getattr(session, "executed_actions", []) or []),
                    )
                )
        except Exception as e:  # a crashed run is a miss, not an abort
            misses.append((i, f"EXC:{type(e).__name__}", str(e)[:140]))
    rate = passes / samples if samples else 0.0
    if printer:
        printer(f"[PROB] {name or 'sample'}: {passes}/{samples} passed ({rate:.0%})")
        for m in misses:
            printer(f"        miss {m}")
    return passes, samples, rate
