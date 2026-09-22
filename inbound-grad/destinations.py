"""Named call destinations, mirroring Grace's legacy page-graph outcomes.

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
        "Be connected to our virtual assistant": Destination(
            "End - Route to Grad ElevenLabs", numbers["ELEVENLABS_NUMBER"], "Graduate ElevenLabs (Ava)"
        ),
        "Be transferred to a queue to talk to a person": Destination(
            "End - Route to Grad", numbers["LIVE_NUMBER"], "Graduate live queue"
        ),
        "Leave a voicemail": Destination(
            "End - Route to TTU Online Grad (voicemail)", numbers["LIVE_NUMBER"], "Graduate live queue"
        ),
    }


def fallback(numbers: dict[str, str]) -> Destination:
    """continue_with didn't match any known choice — e.g. garbled speech-to-text or an
    unexpected value the model returned outside the field's fixed choices. Default to the
    live queue (a human) rather than raising or guessing at the caller's intent. Mirrors
    Grace's own default_route behavior for this playbook family: if nothing else matches,
    default to the live-transfer number."""
    return Destination(
        "End - Route to Grad (fallback)", numbers["LIVE_NUMBER"], "Graduate live queue"
    )


def resolve(numbers: dict[str, str], continue_with: str | None) -> Destination:
    """Returns the Destination for the caller's continue_with answer, falling back to the
    live queue for anything unrecognized rather than returning None (the "Receive a text
    message" choice never reaches here — __main__.py handles it before calling resolve())."""
    return _routes(numbers).get(continue_with, fallback(numbers))
