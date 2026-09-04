"""Shared white-box test helpers for Guava agents. See gotchas/agent-testing.md.

    from agent_testing import (
        advance_until, timeline, scripted_session,   # drive a live session to a state
        pass_rate, judge_bool,            # probabilistic sampling + soft-judge-as-bool
        commands_of, transfers_of, task_ids, suggested_actions,  # inspect the command queue
        capture_call, spy,                # grab the live Call / spy side effects
    )
"""

from .driver import advance_until, scripted_session, timeline
from .sampling import judge_bool, pass_rate
from .probe import (
    capture_call,
    commands_of,
    spy,
    suggested_actions,
    task_ids,
    transfers_of,
)

__all__ = [
    "advance_until",
    "timeline",
    "scripted_session",
    "judge_bool",
    "pass_rate",
    "commands_of",
    "transfers_of",
    "task_ids",
    "suggested_actions",
    "capture_call",
    "spy",
]
