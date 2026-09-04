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
from guava.helpers.rag import DocumentQA

sys.path.insert(0, os.path.dirname(__file__))
import config_sheet
import settings

# Overrides the destination numbers above from the cached "Shared Config" tab (same
# spreadsheet as the FAQ content, shared by all 4 Texas Tech programs) BEFORE
# destinations.py builds its routing table below, so an explicit env var still wins
# but the cache fills in what wasn't set. Cache-only — never touches the network here;
# it's refreshed at deploy time (scripts/prepare-deploy.sh), not on every process
# start, so a Sheets outage can never block the agent from starting.
config_sheet.apply_numbers(settings, {
    "LIVE_NUMBER": "tenk_live",
    "ELEVENLABS_NUMBER": "tenk_elevenlabs",
})

import destinations
from utils import is_open

logger = logging.getLogger("texas_tech.inbound_10k")

# Overrides DocumentQA's default instructions, which literally tell the model to
# say "the answer is not in the provided context" when it can't find one — that
# leaked to a caller verbatim. This phrasing keeps the caller-facing decline
# natural and routes them onward instead.
_DOCUMENT_QA_INSTRUCTIONS = (
    f"You are a phone agent for {settings.ORGANIZATION_NAME}. Answer the caller's "
    "question using ONLY the provided document excerpts, in natural spoken "
    "language — never mention documents, context, or a knowledge base. If the "
    "answer isn't in the excerpts, say you don't have that information on hand "
    "and offer to connect them with a live team member. Do not offer any "
    "follow-ups."
)

_document_qa: DocumentQA | None = None


def _get_document_qa() -> DocumentQA | None:
    # Built lazily on first use, not at import — constructing DocumentQA eagerly ingests
    # the corpus via a live network call on every process start.
    global _document_qa
    if _document_qa is None:
        try:
            faqs = config_sheet.load(settings.FAQ_SPREADSHEET_ID)
            _document_qa = DocumentQA(
                documents=config_sheet.render_corpus(faqs),
                namespace="texas-tech-10k",
                instructions=_DOCUMENT_QA_INSTRUCTIONS,
            )
        except Exception as exc:
            logger.warning("Could not load %s knowledge base: %s", settings.ORGANIZATION_NAME, exc)
    return _document_qa

agent = guava.Agent(
    name=settings.AGENT_NAME,
    organization=settings.ORGANIZATION_NAME,
    purpose=(
        "You are the phone agent for Texas Tech's 10K Degree Completion Program "
        "(DFW / Fort Worth / El Paso). Help callers reach the right place, or capture "
        "their enrollment interest when a live team member isn't available."
    ),
)


@agent.on_call_start
def on_call_start(call: guava.Call):
    logger.info("Call started (session: %s)", call.id)

    call.add_info(
        "Knowledge base scope",
        "Lookups cover general 10K Degree Completion topics — enrollment, credits, "
        "format, and related questions.",
    )

    open_now = is_open()

    if open_now:
        greeting = (
            f"Thank you for calling {settings.ORGANIZATION_NAME}! My name is "
            f"{settings.AGENT_NAME}, your virtual assistant. Please note that this "
            "call may be recorded."
        )
        next_step_field = guava.Field(
            key="next_step",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Be transferred to a queue to talk to a person"],
            description="Ask whether they'd like to be connected to our virtual assistant or transferred to a queue to talk to a person.",
        )
    else:
        greeting = (
            f"Thank you for calling {settings.ORGANIZATION_NAME}! My name is "
            f"{settings.AGENT_NAME}, your virtual assistant. Please note that this "
            "call may be recorded. Our offices are currently closed — live agents "
            "will be available during business hours."
        )
        next_step_field = guava.Field(
            key="next_step",
            field_type="multiple_choice",
            choices=["General information", "Enroll in the program", "Leave a voicemail"],
            description="Ask what they'd like to do.",
        )

    call.set_task(
        "route",
        objective="Figure out what the caller needs, then hand off accordingly.",
        checklist=[
            guava.Say(greeting, key="greeting"),
            next_step_field,
            "Once you know what they need, let them know you're moving forward now. "
            "This task is now complete.",
        ],
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
    (daytime hands enrollment straight to a live agent instead). Every path in the
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
                description="Only if they're interested. Ask for the best number to reach them at.",
            ),
            guava.Field(
                key="email",
                field_type="text",
                required=False,
                description=(
                    "Ask for their email — to add to their enrollment info if "
                    "interested, or to send program details if they're not interested "
                    "but open to receiving info by email."
                ),
            ),
            guava.Field(
                key="contact_preference",
                field_type="multiple_choice",
                required=False,
                choices=["Email", "Phone call"],
                description="Only if they're interested. Ask whether they prefer email or a phone call.",
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
                description="Only if they're interested. Ask how many college credits they currently have.",
            ),
            guava.Field(
                key="location",
                field_type="multiple_choice",
                required=False,
                choices=["Dallas", "Fort Worth", "El Paso"],
                description="Only if they're interested. Ask whether they live in Dallas/Fort Worth or El Paso.",
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
        completion_criteria="Complete once you know whether they're interested and have collected what applies.",
    )


@agent.on_task_complete("enroll")
def on_enroll_complete(call: guava.Call):
    call.hangup(final_instructions="Thank the caller warmly and end the call.")


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    logger.info("Question received: %s", question)
    document_qa = _get_document_qa()
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
    _run_inbound()
