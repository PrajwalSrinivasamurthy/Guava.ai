"""Named call destinations, one row per reachable outcome in Grace's legacy page graph.

This module is the Guava-side mirror of that analysis. settings.py stays the source of
truth for the actual phone numbers; this module only assembles them into a single,
named, keyed table so the routing logic reads as an enumerated list (like Grace's own
page graph) instead of an implicit dict + if/else.
"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Destination:
    grace_outcome: str  # Grace's own outcome_name, for traceability
    number: str | None  # None == hangup, no transfer (enrollment lead-capture path)
    label: str | None  # spoken/log-facing label; None where the generic phrasing is used instead


# Keyed by the caller's next_step answer. "Be connected to our virtual assistant" (open hours)
# and "General information" (after hours) both reach the same ElevenLabs destination; "Be
# transferred to a queue to talk to a person" (open) and "Leave a voicemail" (after hours) both
# reach settings.LIVE_NUMBER under two different Grace outcome names (daytime live transfer vs.
# after-hours voicemail reuse of the same number). "Enroll in the program" never transfers.
ROUTES: dict[str, Destination] = {
    "Be connected to our virtual assistant": Destination(
        "End - Route to 10K ElevenLabs", settings.ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    "General information": Destination(
        "End - Route to 10K ElevenLabs", settings.ELEVENLABS_NUMBER, "our virtual assistant"
    ),
    "Be transferred to a queue to talk to a person": Destination("End - Transfer to Live Agent", settings.LIVE_NUMBER, None),
    "Leave a voicemail": Destination("End - Route to TTU Online (voicemail)", settings.LIVE_NUMBER, None),
    "Enroll in the program": Destination("Enrollment lead capture (hangup, no transfer)", None, None),
}


def resolve(next_step: str | None) -> Destination | None:
    """Returns the Destination for the caller's next_step answer, or None if unrecognized."""
    return ROUTES.get(next_step)
