# agent_testing

Shared white-box test helpers for Guava agents. The **philosophy** lives in the repo-root
[`gotchas/agent-testing.md`](../../gotchas/agent-testing.md); this package is the reusable toolkit that implements it, and
the single place the SDK-private / preview-API coupling (`_command_queue`, `agent._on_call_start`)
is isolated — so an Agent-Testing change is a one-file fix instead of a repo-wide sweep.

Dev/test-only — it is never shipped at runtime.

## Install (per consuming project)

Add it like the other dev path-deps (mirrors `eval_doc_qa`):

```toml
# pyproject.toml
[tool.uv.sources]
agent_testing = { path = "../../../../patterns/agent_testing", editable = true }  # adjust depth

[dependency-groups]
dev = [
    "agent_testing",   # white-box test helpers (dev/test only)
]
```

Then `uv sync`. (The relative path assumes the standard
`customers/<c>/implementations/<u>/` depth — count `../` to `patterns/` for other locations.)

## What's in it

| Helper | Use |
|---|---|
| `commands_of(call, CmdType)` / `transfers_of(call)` / `task_ids(call)` / `suggested_actions(call)` | Inspect the command queue a handler emitted on a `MockCall` (or bare `Call`) after a **direct** handler call. The deepest, deterministic surface. |
| `capture_call(monkeypatch, agent)` | Grab the live `Call` out of an `agent.test()` / `test_roleplay()` session (wraps `agent._on_call_start`) so you can assert `get_field` / `export_fields`. |
| `spy(monkeypatch, module, attr, passthrough=True)` | Wrap a side-effecting function to record `{args, kwargs, result}` — write-spies, param/order/count/negative checks. |
| `advance_until(session, done, answers=, max_turns=, max_turn_seconds=)` | Drive a live session to a target state; returns turns taken (`== max_turns` ⇒ stall); coarse per-turn hang guard. |
| `timeline(session, steps)` | Say each step, snapshot state after each turn → assert *when* things happen. |
| `pass_rate(session_factory, predicate, samples=, name=)` | Sample a roleplay N times, score deterministically, return `(passes, samples, rate)` for a `rate >= threshold` assert. |
| `judge_bool(session, pass_criteria=, fail_criteria=)` | `session.evaluate()` → bool, so the soft judge can be one clause in a sampled test. |

## Examples

**Unit — exact route + destination, offline (`MockCall`):**
```python
from guava.testing import MockCall
from agent_testing import transfers_of, task_ids

call = MockCall(); call.set_field("has_doctor_order", "yes")
mod._route_special_patient_services(call)
xfers = transfers_of(call)
assert xfers and xfers[-1].to_number == live.phones["special_patient_services"]
assert xfers[-1].soft_transfer is True and len(xfers) == 1   # soft, idempotent
assert "appointment_routing" not in task_ids(call)           # negative
```

**Turn-by-turn — routed on the request turn, no stall, exact destination (live):**
```python
from guava.testing import MockCall  # not needed here; shown for contrast
from agent_testing import advance_until, capture_call, spy

def test_dayton(agent_mod, monkeypatch):
    transfers = spy(monkeypatch, agent_mod, "_transfer_to")     # observe the chokepoint
    call_box = capture_call(monkeypatch, agent_mod.agent)
    with agent_mod.agent.test() as session:
        session.wait_for_turn()
        session.say("I'm a Dayton donor and I want to schedule an appointment.")
        turns = advance_until(session, done=lambda s: s.termination_reason == "bot-transfer")
    assert turns < 3                                            # no clarify/confirm/stall
    assert transfers[-1]["args"][1] == "versiti_dayton"         # exact destination
    assert session.get_transcript().count("[caller]:") == 1
```

**Probabilistic — pass rate over a roleplay:**
```python
from agent_testing import pass_rate
p, n, rate = pass_rate(
    lambda: agent_mod.agent.test_roleplay("You feel faint after donating..."),
    predicate=lambda s: "transfer_to_medical_support" in s.executed_actions,
    samples=int(os.environ.get("SAMPLES", "5")), name="medical",
)
assert rate >= float(os.environ.get("PROB_THRESHOLD", "0.8"))
```

Project-specific pieces (config seeding, the concrete mailer/transfer spies, `FakeCall` field
seeding, autouse side-effect neutralizers) stay in each project's `conftest.py`, built *from*
these primitives.
