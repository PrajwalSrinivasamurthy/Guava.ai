"""White-box probes: inspect the command queue a handler emitted, capture the live Call
from a session, and spy on side-effecting functions. See gotchas/agent-testing.md §2.1, §2.4.

This module is the single place the SDK-private / preview coupling lives (``_command_queue``,
``agent._on_call_start``) — if Agent Testing changes shape, fix it here, not in N suites.
"""

from __future__ import annotations

from typing import Any


def commands_of(call: Any, command_type: type) -> list:
    """Every command of `command_type` a handler emitted on this call's queue.

    Works on ``guava.testing.MockCall`` or a bare ``guava.Call`` after a DIRECT handler call
    (unit mode). Filter for ``guava.commands.{TransferCommand, SetTaskCommand,
    ActionSuggestionCommand, SendInstructionCommand, ...}``.
    """
    return [c for c in getattr(call, "_command_queue", []) if isinstance(c, command_type)]


def transfers_of(call: Any) -> list:
    """TransferCommands emitted — assert ``[-1].to_number`` / ``.soft_transfer`` / ``len()``
    (idempotency) / emptiness (no transfer)."""
    from guava.commands import TransferCommand

    return commands_of(call, TransferCommand)


def task_ids(call: Any) -> list[str]:
    """The task_ids a handler set (order preserved) — assert which task the flow dispatched."""
    from guava.commands import SetTaskCommand

    return [c.task_id for c in commands_of(call, SetTaskCommand)]


def suggested_actions(call: Any) -> list:
    """The ActionSuggestionCommand candidate lists emitted (the disambiguation options the
    gate produced) — assert the candidate keys/descriptions deterministically."""
    from guava.commands import ActionSuggestionCommand

    return commands_of(call, ActionSuggestionCommand)


def capture_call(monkeypatch: Any, agent: Any) -> list:
    """Capture the live ``Call`` from an ``agent.test()`` / ``test_roleplay()`` session by
    wrapping ``agent._on_call_start`` (TestSession doesn't expose the call). Returns a list
    that grows to ``[call]`` once the session starts — then assert ``captured[0].get_field(...)``
    / ``.export_fields`` after the run. Auto-restored via ``monkeypatch``.

    If the agent has no ``on_call_start`` handler, spy an always-fired function instead
    (e.g. the transfer chokepoint or a generic ``event()``) with :func:`spy`.
    """
    captured: list = []
    original = getattr(agent, "_on_call_start", None)

    def _wrapped(call):
        captured.append(call)
        if original is not None:
            return original(call)

    monkeypatch.setattr(agent, "_on_call_start", _wrapped)
    return captured


def spy(monkeypatch: Any, module: Any, attr: str, passthrough: bool = True) -> list:
    """Wrap ``module.attr`` to record each call ``{"args", "kwargs", "result"}`` into the
    returned list; auto-restored via ``monkeypatch``.

    ``passthrough=True`` runs the real function (use to observe a side effect while still
    letting it happen against a mock/no-op backend); ``passthrough=False`` neutralizes it
    (returns None). Assert on captured content (write-spy), params, order, count, or that it
    was never called.
    """
    bucket: list = []
    real = getattr(module, attr)

    def _wrapped(*args, **kwargs):
        result = real(*args, **kwargs) if passthrough else None
        bucket.append({"args": args, "kwargs": kwargs, "result": result})
        return result

    monkeypatch.setattr(module, attr, _wrapped)
    return bucket
