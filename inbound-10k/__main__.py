import json
import logging
import os
import sys
import time
from datetime import datetime

import guava
import websockets
from guava import logging_utils
from guava.events import BotSessionEnded

sys.path.insert(0, os.path.dirname(__file__))
import live_config
import settings

# Builds the first FAQ + phone-number snapshot (cache-only — never blocks startup on
# a Sheets outage) BEFORE destinations.py builds its routing table below, so it has
# settings.LIVE_NUMBER / settings.ELEVENLABS_NUMBER applied on the first read too.
# live_config.start_poller() (below, in __main__) re-runs this every
# settings.CONFIG_POLL_SECONDS so later sheet edits show up without a redeploy.
live_config.init()

import destinations
from utils import is_open

logger = logging.getLogger("texas_tech.inbound_10k")

# .env/.env.example name this GUAVA_LOCAL_API_KEY; the SDK's Client (constructed below,
# inside guava.Agent.__init__) only ever reads GUAVA_API_KEY — mirror it across first.
if os.environ.get("GUAVA_LOCAL_API_KEY") and not os.environ.get("GUAVA_API_KEY"):
    os.environ["GUAVA_API_KEY"] = os.environ["GUAVA_LOCAL_API_KEY"]

agent = guava.Agent(
    name=settings.AGENT_NAME,
    organization=settings.ORGANIZATION_NAME,
    purpose=(
        "You are the phone agent for Texas Tech's 10K Degree Completion Program "
        "(DFW / Fort Worth / El Paso). Help callers reach the right place, or capture "
        "their enrollment interest when a live team member isn't available."
    ),
    voice=settings.AGENT_VOICE,
    pronunciations=settings.PRONUNCIATIONS,
)


@agent.on_call_start
def on_call_start(call: guava.Call):
    logger.info("Call started (session: %s)", call.id)
    call.set_language_mode(primary=settings.AGENT_LANGUAGE, secondary=settings.AGENT_SECONDARY_LANGUAGES)

    call.add_info(
        "Knowledge base scope",
        "Lookups cover general 10K Degree Completion topics — enrollment, credits, "
        "format, and related questions.",
    )

    open_now = is_open()

    greeting = (
        f"Thank you for calling {settings.ORGANIZATION_NAME}! My name is "
        f"{settings.AGENT_NAME}, your virtual assistant. Please note that this "
        "call may be recorded."
    )
    closed_notice = None

    if open_now:
        next_step_field = guava.Field(
            key="next_step",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Be transferred to a queue to talk to a person"],
            description=(
                "Ask whether they'd like to be connected to our virtual assistant "
                "or transferred to a queue to talk to a person. If they ask to be "
                "'transferred' but name the virtual assistant, Ava, the AI, or the "
                "bot, that still means the virtual assistant choice — only pick the "
                "queue/person choice when they want a human with no such mention."
            ),
        )
    else:
        # Scripted (not model-phrased) so the three options are always spoken verbatim —
        # a generative Field description left this to the model's discretion, and it would
        # sometimes ask an open "how can I help?" without ever stating the choices.
        closed_notice = guava.Say(
            "Our offices are currently closed — representatives will be available "
            "during business hours. If you have any questions, I can connect you "
            "with our virtual assistant, help you enroll in the program, or take a "
            "voicemail for the team.",
            key="closed_notice",
        )
        next_step_field = guava.Field(
            key="next_step",
            field_type="multiple_choice",
            choices=["General information", "Enroll in the program", "Leave a voicemail"],
            description=(
                "Ask what they'd like to do. If they ask to be transferred to (or "
                "just to talk to) the virtual assistant, Ava, the AI, or the bot, "
                "that's 'General information'."
            ),
        )

    checklist = [guava.Say(greeting, key="greeting")]
    if closed_notice is not None:
        checklist.append(closed_notice)
    checklist += [
        next_step_field,
        "This task is now complete once you know what they need.",
    ]

    call.set_task(
        "route",
        objective="Figure out what the caller needs, then hand off accordingly.",
        checklist=checklist,
        completion_criteria="Complete once next_step is known.",
    )


@agent.on_task_complete("route")
def on_route_complete(call: guava.Call):
    next_step = call.get_field("next_step")
    logger.info("Route choice (session: %s): %r", call.id, next_step)

    if next_step == "Enroll in the program":
        _start_enrollment(call)
        return

    dest = destinations.resolve(next_step)
    call.transfer(
        dest.number,
        instructions=(
            f"Let the caller know you're connecting them to {dest.label} now, then transfer."
            if dest.label
            else "Let the caller know you're connecting them now, then transfer."
        ),
    )


def _start_enrollment(call: guava.Call):
    """Lead-capture funnel — only offered after hours, mirroring the source playbook
    (daytime hands enrollment straight to a representative instead). Every path in the
    source playbook converges on the same outcome regardless of credits/travel/location
    answers, so this task always ends in a hangup with a promised callback, never a
    transfer."""
    call.set_task(
        "enroll",
        objective=(
            "Gather enrollment details so a team member can follow up. Skip any "
            "question that doesn't apply once you know whether they're interested."
        ),
        checklist=[
            guava.Field(
                key="marketing_source",
                field_type="multiple_choice",
                required=False,
                choices=["Billboard", "Online", "Online search", "Search engine", "Social media", "Other"],
                description="Ask how they heard about the program.",
            ),
            guava.Field(
                key="enrollment_interested",
                field_type="multiple_choice",
                choices=["Yes", "No"],
                description=(
                    "Let them know you can gather some information and set up a "
                    "meeting with an advisor, then ask if that would be alright."
                ),
            ),
            guava.Field(
                key="first_name",
                field_type="text",
                required=False,
                description="Only if they're interested. Ask for their first name.",
            ),
            guava.Field(
                key="last_name",
                field_type="text",
                required=False,
                description="Only if they're interested. Ask for their last name.",
            ),
            guava.Field(
                key="phone_number",
                field_type="text",
                required=False,
                description=(
                    "Only if they're interested. Ask for the best number to reach "
                    "them at, spell it back to them to confirm you have it right."
                ),
            ),
            guava.Field(
                key="email",
                field_type="text",
                required=False,
                description=(
                    "Ask for their email — to add to their enrollment info if "
                    "interested, or to send program details if they're not interested "
                    "but open to receiving info by email. Ask them to spell it to "
                    "you. Spell it back to them letter by letter to confirm you have "
                    "it right."
                ),
            ),
            guava.Field(
                key="contact_preference",
                field_type="multiple_choice",
                required=False,
                choices=["Email", "Phone call"],
                description=(
                    "Only if they're interested. Ask whether they prefer email "
                    "or a phone call."
                ),
            ),
            guava.Field(
                key="start_timing",
                field_type="text",
                required=False,
                description="Only if they're interested. Ask when they're hoping to get started.",
            ),
            guava.Field(
                key="college_credits",
                field_type="integer",
                required=False,
                description=(
                    "Only if they're interested. Ask how many college credits "
                    "they currently have."
                ),
            ),
            guava.Field(
                key="location",
                field_type="multiple_choice",
                required=False,
                choices=["Dallas", "Fort Worth", "El Paso", "None of those"],
                description=(
                    "Only if they're interested. Ask whether they live in "
                    "Dallas/Fort Worth or El Paso."
                ),
            ),
            guava.Field(
                key="willing_to_travel",
                field_type="multiple_choice",
                required=False,
                choices=["Yes", "No"],
                description=(
                    "Only if they're interested. Let them know this program meets "
                    "twice a month in person at the Dallas/Fort Worth location in "
                    "Irving, Texas, or at the El Paso location, then ask if they're "
                    "able to travel to make those sessions."
                ),
            ),
            "Thank them for their interest and let them know a team member will "
            "follow up. This task is now complete.",
        ],
        completion_criteria=(
            "Complete once you know whether they're interested and have "
            "collected what applies."
        ),
    )


@agent.on_task_complete("enroll")
def on_enroll_complete(call: guava.Call):
    call.hangup(final_instructions="Thank the caller warmly and end the call.")


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    logger.info("Question received: %s", question)
    document_qa = live_config.get().document_qa
    if document_qa is not None:
        return document_qa.ask(question)
    return (
        "I'm not able to answer that right now — my knowledge base didn't load. "
        f"I can still connect you to the right team at {settings.ORGANIZATION_NAME}."
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded):
    transferred = event.termination_reason == "bot-transfer"
    dest = destinations.resolve(call.get_field("next_step")) if transferred else None

    result = {
        "timestamp": datetime.now().isoformat(),
        "session_id": call.id,
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
        "transfer_number": dest.number if dest else None,
        "transfer_destination": dest.grace_outcome if dest else None,
        "next_step": call.get_field("next_step"),
        "enrollment_interested": call.get_field("enrollment_interested"),
        "first_name": call.get_field("first_name"),
        "last_name": call.get_field("last_name"),
        "phone_number": call.get_field("phone_number"),
        "email": call.get_field("email"),
        "contact_preference": call.get_field("contact_preference"),
        "start_timing": call.get_field("start_timing"),
        "college_credits": call.get_field("college_credits"),
        "location": call.get_field("location"),
        "willing_to_travel": call.get_field("willing_to_travel"),
        "marketing_source": call.get_field("marketing_source"),
    }

    # Same view a production log aggregator sees.
    print(json.dumps(result, indent=2, default=str))

    logger.info(
        "Session complete (session: %s) — next_step=%r enrollment_interested=%r termination=%s "
        "transfer_destination=%r",
        call.id, result["next_step"], result["enrollment_interested"], event.termination_reason,
        result["transfer_destination"],
    )


def _run_inbound():
    RETRY_DELAY = 2
    while True:
        try:
            agent.listen_phone(os.environ["GUAVA_AGENT_NUMBER"])
        except websockets.exceptions.ConnectionClosedError as e:
            logger.warning("Websocket closed: %s; reconnecting in %ss", e, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
        except Exception:
            logger.exception("Listener crashed; restarting in 5s")
            time.sleep(5)


if __name__ == "__main__":
    logging_utils.configure_logging()
    live_config.start_poller(settings.CONFIG_POLL_SECONDS)
    _run_inbound()
