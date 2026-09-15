"""Named call destinations, mirroring Grace's legacy page-graph outcomes for this program.

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


def _routes(numbers: dict[str, str]) -> dict[str, Destination]:
    return {
        "Be connected to our virtual assistant": Destination("End - Route to K12 ElevenLabs", numbers["ELEVENLABS_NUMBER"], "K-12 ElevenLabs (Ava)"),
        "Be transferred to a queue to talk to a person": Destination("End - Route to K12", numbers["LIVE_NUMBER"], "K-12 live queue"),
        "Leave a voicemail": Destination("End - Route to TTU K12 (voicemail)", numbers["LIVE_NUMBER"], "K-12 live queue"),
    }


def resolve(numbers: dict[str, str], continue_with: str | None) -> Destination | None:
    """Returns the Destination for the caller's continue_with answer, or None for a choice
    that doesn't transfer (the text-message path)."""
    return _routes(numbers).get(continue_with)
