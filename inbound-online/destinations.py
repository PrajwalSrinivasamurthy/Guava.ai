"""Named call destinations, one row per reachable outcome in Grace's legacy page graph.

Numbers are passed in from live_config.get().numbers, not read from settings directly —
settings.py stays the source of truth for the hardcoded defaults, but the live value
(refreshed from the sheet every settings.CONFIG_POLL_SECONDS) lives on the LiveConfig
snapshot.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Destination:
    grace_outcome: str  # Grace's own outcome_name, for traceability
    number: str
    label: str  # spoken/log-facing label


# Keyed by the (program, online_service, wants_ai) combination that reaches it. online_service
# is only relevant when program == "Texas Tech Online" and wants_ai is False (every Online
# sub-flavor shares one virtual-assistant destination) — every other combination uses
# online_service=None.
def _routes(numbers: dict[str, str]) -> dict[tuple[str, str | None, bool], Destination]:
    return {
        ("Graduate", None, True): Destination(
            "End - Route to Grad ElevenLabs", numbers["GRAD_ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        ("Graduate", None, False): Destination(
            "End - Route to Grad", numbers["GRAD_NUMBER"], "Graduate live queue"
        ),
        ("K-12", None, True): Destination(
            "End - Route to K12 ElevenLabs", numbers["K12_ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        ("K-12", None, False): Destination(
            "End - Route to K12", numbers["K12_NUMBER"], "K-12 live queue"
        ),
        ("10K Degree Completion", None, True): Destination(
            "End - Route to 10K ElevenLabs", numbers["TENK_ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        ("10K Degree Completion", None, False): Destination(
            "End - Route to 10K", numbers["TENK_NUMBER"], "10K Degree Completion live queue"
        ),
        ("Texas Tech Online", None, True): Destination(
            "End - Route to Online ElevenLabs", numbers["ONLINE_ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        ("Texas Tech Online", "Degree completion / Online Plus", False): Destination(
            "End - Route to Online Signature Plus Rep", numbers["SIGNATURE_PLUS_REP_NUMBER"], "Signature Plus Rep line"
        ),
        ("Texas Tech Online", "Flexible Learning", False): Destination(
            "End - Route to Flexible Learning", numbers["FLEXIBLE_LEARNING_NUMBER"], "Flexible Learning line"
        ),
        ("Texas Tech Online", "Microcredentials", False): Destination(
            "End - Route to Flexible Learning", numbers["FLEXIBLE_LEARNING_NUMBER"], "Flexible Learning line"
        ),
        ("Texas Tech Online", "Career Certificates", False): Destination(
            "End - Route to Flexible Learning", numbers["FLEXIBLE_LEARNING_NUMBER"], "Flexible Learning line"
        ),
    }


def fallback(numbers: dict[str, str]) -> Destination:
    """Caller never named a recognizable program (e.g. picked "Not sure"). Matches
    Grace's "no program named" exit."""
    return Destination(
        "End - Route to Higher Ed Default", numbers["HIGHER_ED_DEFAULT_NUMBER"], "our general support line"
    )


# Confirmed dead in the legacy graph ("provably unreachable") — kept here, never in
# ROUTES/settings.py, purely so a test can assert it stays that way.
UNREACHABLE_SELF_PACED_REP_NUMBER = "+18067424035"


def resolve(numbers: dict[str, str], program: str | None, online_service: str | None, continue_with: str | None) -> Destination:
    """Returns the Destination for the caller's resolved program/service/continue_with answers."""
    # "Leave a voicemail" is only offered after hours, and per SCENARIOS.md's "What is
    # confirmed NOT reachable after hours", no live-queue/rep-line number is reachable in
    # the legacy AH playbook — only Higher Ed Default and the 4 ElevenLabs numbers. Route
    # it to fallback() instead of falling through to the program's (daytime) live queue.
    if continue_with == "Leave a voicemail":
        return fallback(numbers)
    wants_ai = continue_with == "Be connected to our virtual assistant"
    key_service = online_service if program == "Texas Tech Online" and not wants_ai else None
    return _routes(numbers).get((program, key_service, wants_ai), fallback(numbers))
