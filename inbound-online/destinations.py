"""Named call destinations, one row per reachable outcome in Grace's legacy page graph.

settings.py stays the source of truth for the actual phone numbers; this module only
assembles them into a single, named, keyed table so the routing logic reads as an
enumerated list (like Grace's own page graph) instead of two implicit dicts + an if/else.
"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Destination:
    grace_outcome: str  # Grace's own outcome_name, for traceability
    number: str
    label: str  # spoken/log-facing label


# Keyed by the (program, online_service, wants_ai) combination that reaches it. online_service
# is only relevant when program == "Texas Tech Online" and wants_ai is False (every Online
# sub-flavor shares one virtual-assistant destination) — every other combination uses
# online_service=None.
ROUTES: dict[tuple[str, str | None, bool], Destination] = {
    ("Graduate", None, True): Destination(
        "End - Route to Grad ElevenLabs", settings.GRAD_ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    ("Graduate", None, False): Destination(
        "End - Route to Grad", settings.GRAD_NUMBER, "Graduate live queue"
    ),
    ("K-12", None, True): Destination(
        "End - Route to K12 ElevenLabs", settings.K12_ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    ("K-12", None, False): Destination(
        "End - Route to K12", settings.K12_NUMBER, "K-12 live queue"
    ),
    ("10K Degree Completion", None, True): Destination(
        "End - Route to 10K ElevenLabs", settings.TENK_ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    ("10K Degree Completion", None, False): Destination(
        "End - Route to 10K", settings.TENK_NUMBER, "10K Degree Completion live queue"
    ),
    ("Texas Tech Online", None, True): Destination(
        "End - Route to Online ElevenLabs", settings.ONLINE_ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    ("Texas Tech Online", "Degree completion / Online Plus", False): Destination(
        "End - Route to Online Signature Plus Rep", settings.SIGNATURE_PLUS_REP_NUMBER, "Signature Plus Rep line"
    ),
    ("Texas Tech Online", "Flexible Learning", False): Destination(
        "End - Route to Flexible Learning", settings.FLEXIBLE_LEARNING_NUMBER, "Flexible Learning line"
    ),
    ("Texas Tech Online", "Microcredentials", False): Destination(
        "End - Route to Flexible Learning", settings.FLEXIBLE_LEARNING_NUMBER, "Flexible Learning line"
    ),
    ("Texas Tech Online", "Career Certificates", False): Destination(
        "End - Route to Flexible Learning", settings.FLEXIBLE_LEARNING_NUMBER, "Flexible Learning line"
    ),
}

# Caller never named a recognizable program (e.g. picked "Not sure"). Matches Grace's
# "no program named" exit.
FALLBACK = Destination(
    "End - Route to Higher Ed Default", settings.HIGHER_ED_DEFAULT_NUMBER, "our general support line"
)

# Confirmed dead in the legacy graph ("provably unreachable") — kept here, never in
# ROUTES/settings.py, purely so a test can assert it stays that way.
UNREACHABLE_SELF_PACED_REP_NUMBER = "+18067424035"


def resolve(program: str | None, online_service: str | None, continue_with: str | None) -> Destination:
    """Returns the Destination for the caller's resolved program/service/continue_with answers."""
    # "Leave a voicemail" is only offered after hours, and per SCENARIOS.md's "What is
    # confirmed NOT reachable after hours", no live-queue/rep-line number is reachable in
    # the legacy AH playbook — only Higher Ed Default and the 4 ElevenLabs numbers. Route
    # it to FALLBACK instead of falling through to the program's (daytime) live queue.
    if continue_with == "Leave a voicemail":
        return FALLBACK
    wants_ai = continue_with == "Be connected to our virtual assistant"
    key_service = online_service if program == "Texas Tech Online" and not wants_ai else None
    return ROUTES.get((program, key_service, wants_ai), FALLBACK)
