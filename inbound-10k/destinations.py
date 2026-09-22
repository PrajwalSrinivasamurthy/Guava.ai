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
    number: str | None  # None == hangup, no transfer (enrollment lead-capture path)
    label: str | None  # spoken/log-facing label; None where the generic phrasing is used instead


# Keyed by the caller's next_step answer. "Be connected to our virtual assistant" (open hours)
# and "General information" (after hours) both reach the same ElevenLabs destination; "Be
# transferred to a queue to talk to a person" (open) and "Leave a voicemail" (after hours) both
# reach numbers["LIVE_NUMBER"] under two different Grace outcome names (daytime live transfer vs.
# after-hours voicemail reuse of the same number). "Enroll in the program" never transfers.
def _routes(numbers: dict[str, str]) -> dict[str, Destination]:
    return {
        "Be connected to our virtual assistant": Destination(
            "End - Route to 10K ElevenLabs", numbers["ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        "General information": Destination(
            "End - Route to 10K ElevenLabs", numbers["ELEVENLABS_NUMBER"], "our virtual assistant"
        ),
        "Be transferred to a queue to talk to a person": Destination("End - Transfer to Live Agent", numbers["LIVE_NUMBER"], None),
        "Leave a voicemail": Destination("End - Route to TTU Online (voicemail)", numbers["LIVE_NUMBER"], None),
        "Enroll in the program": Destination("Enrollment lead capture (hangup, no transfer)", None, None),
    }


def fallback(numbers: dict[str, str]) -> Destination:
    """next_step didn't match any known choice — e.g. garbled speech-to-text or an
    unexpected value the model returned outside the field's fixed choices. Default to the
    live queue (a human) rather than raising or guessing at the caller's intent — matches
    the documented default_route behavior across this playbook family: if nothing else
    matches, default to the live-transfer number."""
    return Destination(
        "End - Transfer to Live Agent (fallback)", numbers["LIVE_NUMBER"], None
    )


def resolve(numbers: dict[str, str], next_step: str | None) -> Destination:
    """Returns the Destination for the caller's next_step answer, falling back to the live
    queue for anything unrecognized rather than returning None ("Enroll in the program"
    never reaches here — __main__.py handles it before calling resolve())."""
    return _routes(numbers).get(next_step, fallback(numbers))
