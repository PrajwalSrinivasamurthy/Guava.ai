import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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
# start, so a Sheets outage can never block the agent from starting. Online is the one
# program that consumes every key, since it's the front door for all 4 programs'
# destinations.
config_sheet.apply_numbers(settings, {
    "SIGNATURE_PLUS_REP_NUMBER": "signature_plus_rep",
    "HIGHER_ED_DEFAULT_NUMBER": "higher_ed_default",
    "FLEXIBLE_LEARNING_NUMBER": "flexible_learning",
    "GRAD_NUMBER": "grad_live",
    "K12_NUMBER": "k12_live",
    "TENK_NUMBER": "tenk_live",
    "ONLINE_ELEVENLABS_NUMBER": "online_elevenlabs",
    "K12_ELEVENLABS_NUMBER": "k12_elevenlabs",
    "GRAD_ELEVENLABS_NUMBER": "grad_elevenlabs",
    "TENK_ELEVENLABS_NUMBER": "tenk_elevenlabs",
})

import destinations
from utils import holiday_name, is_open

logger = logging.getLogger("texas_tech.inbound_online")

CURRENT_DIR = Path(__file__).resolve().parent

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
                namespace="texas-tech-online",
                instructions=_DOCUMENT_QA_INSTRUCTIONS,
            )
        except Exception as exc:
            logger.warning("Could not load Texas Tech Online knowledge base: %s", exc)
    return _document_qa

# .env/.env.example name this GUAVA_LOCAL_API_KEY; the SDK's Client (constructed below,
# inside guava.Agent.__init__) only ever reads GUAVA_API_KEY — mirror it across first.
if os.environ.get("GUAVA_LOCAL_API_KEY") and not os.environ.get("GUAVA_API_KEY"):
    os.environ["GUAVA_API_KEY"] = os.environ["GUAVA_LOCAL_API_KEY"]

agent = guava.Agent(
    name=settings.AGENT_NAME,
    organization=settings.ORGANIZATION_NAME,
    purpose=(
        "You are the front-door phone agent for Texas Tech Online. You help callers "
        "reach the right place: Texas Tech Online's own services (Online Plus / degree "
        "completion, Flexible Learning, Microcredentials, Career Certificates), or Texas "
        "Tech's Graduate, K-12, or 10K Degree Completion programs. Answer general "
        "questions about Texas Tech Online from your knowledge base along the way."
    ),
    voice=settings.AGENT_VOICE,
    pronunciations=settings.PRONUNCIATIONS,
)


def _build_route_task(call: guava.Call, opener: guava.Say | str):
    """Builds and sets the "route" task's checklist. `opener` is the first checklist
    item — the initial greeting on a fresh call, or a plain-string "still helping"
    transition when re-opened after a caller stayed unsure of their program."""
    open_now = is_open()
    holiday = None if open_now else holiday_name()

    if open_now:
        continue_field = guava.Field(
            key="continue_with",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Be transferred to a queue to talk to a person"],
            description=(
                "Only ask this once a specific program is known. Ask whether they'd "
                "like to be connected to our virtual assistant or transferred to a "
                "queue to talk to a person."
            ),
            required=False,
        )
        closed_notice = None
    else:
        continue_field = guava.Field(
            key="continue_with",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Leave a voicemail"],
            description=(
                "Only ask this once a specific program is known. Let them know our "
                "live team isn't available right now, then ask whether they'd like to "
                "be connected to our virtual assistant or leave a voicemail."
            ),
            required=False,
        )
        if holiday:
            closed_notice = guava.Say(
                f"Our offices are currently closed in observance of {holiday}. If you have "
                "any questions, I can connect you with our virtual assistant, or I can "
                "transfer you to our support center to leave a voicemail.",
                key="closed_notice",
            )
        else:
            closed_notice = guava.Say(
                "Our offices are currently closed. Live agents will be available during "
                "business hours. If you have any questions, I can connect you with our "
                "virtual assistant, or I can transfer you to our support center to "
                "leave a voicemail.",
                key="closed_notice",
            )

    checklist = [opener]
    if closed_notice is not None:
        checklist.append(closed_notice)
    checklist += [
        "If the caller already mentioned what the program they are asking about, fill in program directly.",
        guava.Field(
            key="program",
            field_type="multiple_choice",
            choices=["Texas Tech Online", "Graduate", "K-12", "10K Degree Completion", "Not sure"],
            description="Ask which program the caller is calling about.",
        ),
        guava.Field(
            key="online_service",
            field_type="multiple_choice",
            choices=["Degree completion / Online Plus", "Flexible Learning", "Microcredentials", "Career Certificates"],
            description=(
                "Only ask this when the caller selected Texas Tech Online above. Ask "
                "which of these services they need."
            ),
            required=False,
        ),
        continue_field,
        "Once you know where the caller needs to go, let them know you're connecting "
        "them now. This task is now complete.",
    ]

    if open_now:
        completion_criteria = (
            "Complete once program is a specific program (Texas Tech Online, Graduate, "
            "K-12, or 10K Degree Completion) and continue_with is known. If the caller "
            "remains unsure which program they need, keep answering their questions "
            "instead — do not ask continue_with and do not complete this task."
        )
    else:
        completion_criteria = (
            "Complete once program is known. If program is 'Not sure', complete "
            "immediately — do not ask continue_with. Otherwise, complete once "
            "continue_with is also known."
        )

    call.set_task(
        "route",
        objective=(
            "Route the caller to the right place based on the answers below; answer "
            "general Texas Tech Online questions from your knowledge base along the way."
        ),
        checklist=checklist,
        completion_criteria=completion_criteria,
    )


@agent.on_call_start
def on_call_start(call: guava.Call):
    logger.info("Call started (session: %s)", call.id)
    call.set_language_mode(primary=settings.AGENT_LANGUAGE, secondary=settings.AGENT_SECONDARY_LANGUAGES)

    call.add_info(
        "Knowledge base scope",
        "Lookups cover general Texas Tech Online topics — programs, enrollment, courses, "
        "and costs — not Grad, K-12, or 10K specifics.",
    )

    greeting = guava.Say(
        f"Thank you for calling Texas Tech Online! My name is {settings.AGENT_NAME}, "
        "your virtual assistant. Please note that this call may be recorded.",
        key="greeting",
    )
    _build_route_task(call, greeting)


@agent.on_task_complete("route")
def on_route_complete(call: guava.Call):
    program = call.get_field("program")
    online_service = call.get_field("online_service")
    continue_with = call.get_field("continue_with")

    if program == "Not sure":
        if is_open():
            # No destination exists for "unsure which program, during business hours" —
            # keep the caller talking to the bot instead of transferring anywhere.
            logger.info("Caller unsure of program, staying with the bot (session: %s)", call.id)
            _build_route_task(
                call,
                "The caller wasn't sure which program they needed and wants to keep "
                "talking with you. Let them know that's fine, then keep helping them "
                "and try again to figure out which program they're calling about.",
            )
            return
        # After hours, an unresolved program always falls back to the Higher Ed
        # Default voicemail, regardless of continue_with (which isn't asked for this
        # case at all).
        dest = destinations.FALLBACK
    else:
        dest = destinations.resolve(program, online_service, continue_with)

    logger.info(
        "Routing call (session: %s) program=%r online_service=%r continue_with=%r -> %s (%s)",
        call.id, program, online_service, continue_with, dest.number, dest.grace_outcome,
    )
    call.transfer(
        dest.number,
        instructions=f"Let the caller know you're connecting them to {dest.label} now, then transfer.",
    )


@agent.on_escalate
def on_escalate_handler(call: guava.Call) -> None:
    logger.info("Escalation triggered (session: %s)", call.id)
    continue_with = "Be transferred to a live team member" if is_open() else "Leave a voicemail"
    dest = destinations.resolve(call.get_field("program"), call.get_field("online_service"), continue_with)
    call.transfer(
        dest.number,
        instructions=f"Let the caller know you're connecting them to {dest.label} now, then transfer.",
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    logger.info("Question received: %s", question)
    document_qa = _get_document_qa()
    if document_qa is not None:
        return document_qa.ask(question)
    return (
        "I'm not able to answer that right now, I'm having connection issues. "
        f"I can still connect you to the right team at {settings.ORGANIZATION_NAME}."
    )


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded):
    transferred = event.termination_reason == "bot-transfer"
    dest = (
        destinations.resolve(call.get_field("program"), call.get_field("online_service"), call.get_field("continue_with"))
        if transferred
        else None
    )

    result = {
        "timestamp": datetime.now().isoformat(),
        "session_id": call.id,
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
        "program": call.get_field("program"),
        "online_service": call.get_field("online_service"),
        "continue_with": call.get_field("continue_with"),
        "transfer_number": dest.number if dest else None,
        "transfer_destination": dest.label if dest else None,
    }

    # Same view a production log aggregator sees.
    print(json.dumps(result, indent=2, default=str))

    logger.info(
        "Routing complete (session: %s) — program=%r continue_with=%r termination=%s "
        "transfer_destination=%r",
        call.id, result["program"], result["continue_with"], event.termination_reason,
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
