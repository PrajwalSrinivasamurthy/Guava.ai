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

sys.path.insert(0, os.path.dirname(__file__))
import live_config
import settings

# Builds the first FAQ + phone-number snapshot (cache-only — never blocks startup on
# a Sheets outage) BEFORE destinations.py builds its routing table below, so it has
# every *_NUMBER setting applied on the first read too. Online is the one program that
# consumes every key, since it's the front door for all 4 programs' destinations.
# live_config.start_poller() (below, in __main__) re-runs this every
# settings.CONFIG_POLL_SECONDS so later sheet edits show up without a redeploy.
live_config.init()

import destinations
from utils import holiday_name, is_open

logger = logging.getLogger("texas_tech.inbound_online")

CURRENT_DIR = Path(__file__).resolve().parent

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
                "queue to talk to a person. If they ask to be 'transferred' but name "
                "the virtual assistant, Ava, the AI, or the bot, that still means the "
                "virtual assistant choice — only pick the queue/person choice when "
                "they want a human with no such mention."
            ),
            required=False,
        )
        closed_notice_text = None
    else:
        continue_field = guava.Field(
            key="continue_with",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Leave a voicemail"],
            description=(
                "Only ask this once a specific program is known. Let them know our "
                "live team isn't available right now, then ask whether they'd like to "
                "be connected to our virtual assistant or leave a voicemail. If they ask "
                "for the virtual assistant, Ava, the AI, or the bot by name, that's 'Be "
                "connected to our virtual assistant' — don't treat Ava as an unavailable "
                "person."
            ),
            required=False,
        )
        if holiday:
            closed_notice_text = (
                f"Our offices are currently closed in observance of {holiday}. If you have "
                "any questions, I can connect you with our virtual assistant, or I can "
                "transfer you to our support center to leave a voicemail."
            )
        else:
            closed_notice_text = (
                "Our offices are currently closed. Representatives will be available during "
                "business hours. If you have any questions, I can connect you with our "
                "virtual assistant, or I can transfer you to our support center to "
                "leave a voicemail."
            )

    # Fold into the opener rather than a second back-to-back Say item — the checklist
    # should never have two consecutive Say items. The opener is a plain string (not a
    # Say) on the "still unsure" loop-back path, which never reaches here with
    # closed_notice_text set (that loop only runs during open hours) — kept as a
    # separate checklist item in that hypothetical case since a plain string is a
    # paraphrasable instruction, not a verbatim statement to merge with.
    if closed_notice_text and isinstance(opener, guava.Say):
        opener = guava.Say(f"{opener.statement} {closed_notice_text}", key=opener.key)
        closed_notice_text = None

    checklist = [opener]
    if closed_notice_text:
        checklist.append(closed_notice_text)
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
        "This task is now complete once you know where the caller needs to go.",
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
        dest = destinations.fallback(live_config.get().numbers)
    else:
        dest = destinations.resolve(live_config.get().numbers, program, online_service, continue_with)

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
    dest = destinations.resolve(live_config.get().numbers, call.get_field("program"), call.get_field("online_service"), continue_with)
    call.transfer(
        dest.number,
        instructions=f"Let the caller know you're connecting them to {dest.label} now, then transfer.",
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    logger.info("Question received: %s", question)
    document_qa = live_config.get().document_qa
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
        destinations.resolve(live_config.get().numbers, call.get_field("program"), call.get_field("online_service"), call.get_field("continue_with"))
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
    live_config.start_poller(settings.CONFIG_POLL_SECONDS)
    _run_inbound()
