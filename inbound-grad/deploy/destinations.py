"""Named call destinations, mirroring Grace's legacy page-graph outcomes.

settings.py stays the source of truth for the actual phone numbers; this module only
assembles them into a named, keyed table.
"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Destination:
    grace_outcome: str  # Grace's own outcome_name, for traceability
    number: str
    label: str  # spoken/log-facing label


ROUTES: dict[str, Destination] = {
    "Be connected to our virtual assistant": Destination(
        "End - Route to Grad ElevenLabs", settings.ELEVENLABS_NUMBER, "Graduate ElevenLabs (Ava)"
    ),
    "Be transferred to a queue to talk to a person": Destination(
        "End - Route to Grad", settings.LIVE_NUMBER, "Graduate live queue"
    ),
    "Leave a voicemail": Destination(
        "End - Route to TTU Online Grad (voicemail)", settings.LIVE_NUMBER, "Graduate live queue"
    ),
}


def resolve(continue_with: str | None) -> Destination | None:
    """Returns the Destination for the caller's continue_with answer, or None for a choice
    that doesn't transfer (the text-message path)."""
    return ROUTES.get(continue_with)
