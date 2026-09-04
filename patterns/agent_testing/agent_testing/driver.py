"""Turn-by-turn drivers for live Guava test sessions (``agent.test()`` /
``agent.test_roleplay()``). See gotchas/agent-testing.md §2.6 and §7.

These fast-forward a conversation to a target state so a test can assert *when* things
happen (routing, latency, no-stall) rather than only reading the wreckage at the end.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Callable


def advance_until(
    session: Any,
    done: Callable[[Any], bool],
    answers: list[str] | None = None,
    max_turns: int = 10,
    max_turn_seconds: float = 25.0,
) -> int:
    """Drive `session` forward until ``done(session)`` is True, and return the number of
    caller turns taken.

    Each iteration: check ``done`` → let the agent take its turn (``wait_for_turn`` itself
    fast-forwards the agent's filler/state utterances to the caller's next turn) → check
    ``done`` again → speak the next scripted answer (or a neutral nudge if ``answers`` is
    exhausted).

    Semantics the caller asserts on:
      * **Return value == turns taken.** Reaching ``max_turns`` without ``done`` is the
        STALL signal (``assert advance_until(...) < N``).
      * A transfer/hangup ends the call; the underlying ``ConnectionClosedOK`` is caught and
        the turns-so-far returned.
      * **Coarse latency guard:** a single agent turn that takes longer than
        ``max_turn_seconds`` raises ``AssertionError``. Keep the ceiling generous — it is a
        hang detector, not a performance gate (wall-clock over a live LLM+network is noisy).

    NOTE: this catches a *slow-but-completing* turn. A truly infinite hang (agent never
    yields) blocks inside ``wait_for_turn``; guard that at the suite level (e.g.
    pytest-timeout).
    """
    from websockets.exceptions import ConnectionClosedOK

    remaining = list(answers or [])
    for turn in range(max_turns):
        if done(session):
            return turn
        started = time.monotonic()
        try:
            session.wait_for_turn()
        except ConnectionClosedOK:
            return turn
        elapsed = time.monotonic() - started
        if elapsed > max_turn_seconds:
            raise AssertionError(
                f"Dialog Engine took {elapsed:.0f}s on turn {turn} "
                f"(ceiling {max_turn_seconds:.0f}s) — excessive / possible hang"
            )
        if done(session):
            return turn
        session.say(remaining.pop(0) if remaining else "Yes, please go ahead.")
    return max_turns


def timeline(session: Any, steps: list[str]) -> list[dict]:
    """Say each utterance in `steps`, snapshotting session state AFTER each agent turn, so
    a test can assert *when* each thing happened.

    Returns one frame per step: ``{"said", "actions", "termination_reason", "caller_turns"}``.
    Assert, e.g., that a transfer appears only in the final frame (a multi-step gate wasn't
    short-circuited).
    """
    from websockets.exceptions import ConnectionClosedOK

    frames: list[dict] = []
    for said in steps:
        session.say(said)
        try:
            session.wait_for_turn()
        except ConnectionClosedOK:
            pass
        frames.append(
            {
                "said": said,
                "actions": list(getattr(session, "executed_actions", []) or []),
                "termination_reason": getattr(session, "termination_reason", None),
                "caller_turns": session.get_transcript().count("[caller]:"),
            }
        )
    return frames


@contextmanager
def scripted_session(agent: Any, **test_kwargs: Any):
    """Open ``agent.test()`` for a hand-scripted turn-by-turn drive, tolerating the clean
    WebSocket close (``ConnectionClosedOK``, code 1000) that a transfer or hangup triggers
    mid-drive — the context-manager counterpart to ``advance_until``'s close handling, for
    tests that call ``say``/``wait_for_turn``/``wait_for_end`` directly.

    Usage::

        with scripted_session(agent) as session:
            session.wait_for_turn()
            session.say("...")
            session.wait_for_end()
        r = record(session, "...")          # assert on the transcript AFTER the block

    A clean close raised anywhere inside the block is swallowed so control resumes after the
    block with the transcript captured so far. This does NOT mask real failures: a genuinely
    premature close leaves the substantive post-block assertions (reached-transfer, action
    fired, ZIP-asked-once, …) to fail as they should. Passes ``**test_kwargs`` through to
    ``agent.test()`` (e.g. ``variables=``).
    """
    from websockets.exceptions import ConnectionClosedOK

    with agent.test(**test_kwargs) as session:
        try:
            yield session
        except ConnectionClosedOK:
            pass
