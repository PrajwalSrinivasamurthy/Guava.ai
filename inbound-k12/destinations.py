"""Named call destinations, mirroring Grace's legacy page-graph outcomes for this program.

This module is the Guava-side mirror of that table for K-12. settings.py stays the
source of truth for the actual phone numbers; this module only assembles them into a
named, keyed table.
"""

from dataclasses import dataclass

import settings


@dataclass(frozen=True)
class Destination:
    grace_outcome: str  # Grace's own outcome_name, for traceability
    number: str
    label: str  # spoken/log-facing label


ROUTES: dict[str, Destination] = {
    "Be connected to our virtual assistant": Destination("End - Route to K12 ElevenLabs", settings.ELEVENLABS_NUMBER, "K-12 ElevenLabs (Ava)"),
    "Be transferred to a queue to talk to a person": Destination("End - Route to K12", settings.LIVE_NUMBER, "K-12 live queue"),
    "Leave a voicemail": Destination("End - Route to TTU K12 (voicemail)", settings.LIVE_NUMBER, "K-12 live queue"),
}


def resolve(continue_with: str | None) -> Destination | None:
    """Returns the Destination for the caller's continue_with answer, or None for a choice
    that doesn't transfer (the text-message path)."""
    return ROUTES.get(continue_with)
