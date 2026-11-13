import json
import logging
import os
import sys
import threading
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

import assist
import destinations
import kb_client
import sms
from utils import holiday_name, is_open

logger = logging.getLogger("texas_tech.inbound_cla")

# .env/.env.example name this GUAVA_LOCAL_API_KEY; the SDK's Client (constructed below,
# inside guava.Agent.__init__) only ever reads GUAVA_API_KEY — mirror it across first.
if os.environ.get("GUAVA_LOCAL_API_KEY") and not os.environ.get("GUAVA_API_KEY"):
    os.environ["GUAVA_API_KEY"] = os.environ["GUAVA_LOCAL_API_KEY"]

# Present when the knowledge service is configured: the agent then answers questions
# itself instead of handing callers to the virtual assistant.
kb = (
    kb_client.KbClient(settings.KB_SERVICE_URL, settings.KB_API_KEY, settings.KB_TIMEOUT_SECONDS)
    if settings.KB_ENABLED and settings.KB_SERVICE_URL and settings.KB_API_KEY
    else None
)

agent = guava.Agent(
    name=settings.AGENT_NAME,
    organization=settings.ORGANIZATION_NAME,
    purpose=(
        f"You are the phone assistant for {settings.ORGANIZATION_NAME}. Answer callers' "
        "questions about it, and connect them to our support center when they ask for a person."
        if kb is not None else
        f"You are the phone agent for {settings.ORGANIZATION_NAME}. Help callers "
        "reach the right place — either connect them to our virtual assistant or "
        "to a live team member."
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
        "Lookups cover general Career Learning Academy topics.",
    )

    if kb is not None:
        # Open the connection to the knowledge service while the greeting plays.
        threading.Thread(target=kb.warm, name="kb-warm", daemon=True).start()
        _start_assist_task(call)
        return

    open_now = is_open()

    greeting_text = (
        f"Thank you for calling {settings.ORGANIZATION_NAME}! My name is "
        f"{settings.AGENT_NAME}, your virtual assistant. Please note that this "
        "call may be recorded."
    )

    if open_now:
        continue_field = guava.Field(
            key="continue_with",
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
        holiday = holiday_name()
        # Fold into the single greeting Say rather than a second back-to-back Say item —
        # the checklist should never have two consecutive Say items.
        if holiday:
            greeting_text += (
                f" Our offices are currently closed in observance of {holiday}. If you have "
                "any questions, I will transfer you to our virtual assistant. You can "
                "also choose to leave a voicemail for the team, or receive a text message "
                "with a link to more information."
            )
        else:
            greeting_text += (
                " Our offices are currently closed. Representatives will be available during "
                "business hours. If you have any questions, I will transfer you to our "
                "virtual assistant. You can also choose to leave a voicemail for the "
                "team, or receive a text message with a link to more information."
            )
        continue_field = guava.Field(
            key="continue_with",
            field_type="multiple_choice",
            choices=["Be connected to our virtual assistant", "Leave a voicemail", "Receive a text message"],
            description=(
                "Let them know our live team isn't available right now, then ask whether "
                "they'd like to be connected to our virtual assistant, leave a voicemail, "
                "or receive a text message with a link to more information. If they ask "
                "for the virtual assistant, Ava, the AI, or the bot by name, that's 'Be "
                "connected to our virtual assistant' — don't treat Ava as an unavailable "
                "person."
            ),
        )

    checklist = [guava.Say(greeting_text, key="greeting")]
    checklist += [
        continue_field,
        "This task is now complete once you know where the caller needs to go.",
    ]

    call.set_task(
        "route",
        objective=(
            "Determine whether the caller wants to be connected to our virtual "
            f"assistant or transferred, then hand off. Answer general questions "
            f"about {settings.ORGANIZATION_NAME} along the way."
        ),
        checklist=checklist,
        completion_criteria="Complete once continue_with is known.",
    )


def _start_assist_task(call: guava.Call):
    open_now = is_open()
    offer_text = bool(settings.CLA_AH_TEXT_URL)

    call.set_task(
        "assist",
        objective=(
            f"Answer the caller's questions about {settings.ORGANIZATION_NAME}. If they want "
            "a person, hand off; if they have no more questions, wrap up."
        ),
        checklist=[
            guava.Say(assist.greeting(open_now, None if open_now else holiday_name(), offer_text), key="greeting"),
            assist.outcome_field(open_now, offer_text),
            "Keep answering questions. This task is complete only once the caller asks for a person "
            "or says they're finished; don't ask whether they have more questions after each answer.",
        ],
        completion_criteria="Complete once the caller has said they want a person or are finished.",
    )


@agent.on_task_complete("route")
def on_route_complete(call: guava.Call):
    continue_with = call.get_field("continue_with")

    if continue_with == "Receive a text message":
        _send_text_and_hang_up(call)
        return

    _transfer(call, continue_with)


@agent.on_task_complete("assist")
def on_assist_complete(call: guava.Call):
    outcome = call.get_field("outcome")
    logger.info("Assist task complete (session: %s) outcome=%r", call.id, outcome)

    if outcome == assist.TEXT_MESSAGE:
        _send_text_and_hang_up(call)
    elif outcome == assist.DONE:
        call.hangup(final_instructions=f"Thank them for calling {settings.ORGANIZATION_NAME} and say goodbye.")
    else:
        _transfer(call, outcome)


def _send_text_and_hang_up(call: guava.Call):
    from_number = getattr(call.call_info, "from_number", None)
    sent = sms.send_link(
        from_number, settings.CLA_AH_TEXT_URL,
        f"{settings.ORGANIZATION_NAME} — more information:",
    )
    logger.info("Text-message hand-off (session: %s) sent=%s", call.id, sent)
    call.hangup(final_instructions=(
        "Let them know you've sent the text with the link, then "
        "say goodbye."
        if sent else
        "Apologize that the text couldn't be sent right now, let them know someone will "
        "follow up, then say goodbye."
    ))


def _transfer(call: guava.Call, choice: str | None):
    dest = destinations.resolve(live_config.get().numbers, choice)
    if not dest.number:
        logger.warning("No number configured for %s (session: %s); not transferring.", dest.label, call.id)
        call.hangup(final_instructions=(
            "Apologize that you can't connect them right now, let them know someone will "
            "follow up, then say goodbye."
        ))
        return

    logger.info(
        "Routing call (session: %s) choice=%r -> %s (%s)",
        call.id, choice, dest.number, dest.grace_outcome,
    )
    call.transfer(
        dest.number,
        instructions=f"Let the caller know you're connecting them to {dest.spoken} now, then transfer.",
    )


@agent.on_question
def on_question(call: guava.Call, question: str) -> str:
    if kb is not None:
        return _answer_from_kb(question)

    document_qa = live_config.get().document_qa
    if document_qa is not None:
        return document_qa.ask(question)
    return (
        "I'm not able to answer that right now — my knowledge base didn't load. "
        f"I can still connect you to the right team at {settings.ORGANIZATION_NAME}."
    )


def _answer_from_kb(question: str) -> str:
    try:
        answer = kb.ask(question)
    except kb_client.KbUnavailable as error:
        logger.warning("Knowledge service unavailable: %s", error)
        return settings.KB_FALLBACK_MESSAGE
    logger.info("Knowledge service answered found=%s", answer.found)
    return answer.text if answer.found else settings.KB_FALLBACK_MESSAGE


@agent.on_session_end
def on_session_end(call: guava.Call, event: BotSessionEnded):
    transferred = event.termination_reason == "bot-transfer"
    choice = call.get_field("continue_with") or call.get_field("outcome")
    dest = destinations.resolve(live_config.get().numbers, choice) if transferred else None

    result = {
        "timestamp": datetime.now().isoformat(),
        "session_id": call.id,
        "termination_reason": event.termination_reason,
        "dnc": event.dnc,
        "choice": choice,
        "transfer_number": dest.number if dest else None,
        "transfer_destination": dest.label if dest else None,
    }

    print(json.dumps(result, indent=2, default=str))

    logger.info(
        "Routing complete (session: %s) — choice=%r termination=%s "
        "transfer_destination=%r",
        call.id, choice, event.termination_reason,
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
