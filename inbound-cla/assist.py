"""Wording and fields for the flow where the agent answers questions itself (see
settings.KB_SERVICE_URL), extracted from __main__.py so the call flow reads without noise."""

import guava

import settings

TRANSFER = "Transfer to a person"
VOICEMAIL = "Leave a voicemail"
TEXT_MESSAGE = "Receive a text message"
DONE = "No more questions"


def greeting(open_now: bool, holiday: str | None, offer_text: bool) -> str:
    text = (
        f"Thank you for calling {settings.ORGANIZATION_NAME}! My name is "
        f"{settings.AGENT_NAME}, your virtual assistant. Please note that this "
        "call may be recorded."
    )
    if open_now:
        return text + " I can answer your questions, or connect you with our support center. How can I help you today?"

    if holiday:
        text += f" Our offices are currently closed in observance of {holiday}."
    else:
        text += " Our offices are currently closed. Representatives will be available during business hours."
    after_hours_options = "leave a voicemail for the team"
    if offer_text:
        after_hours_options += " or receive a text message with a link to more information"
    return text + f" I can answer your questions, and you can also {after_hours_options}. How can I help you today?"


def outcome_field(open_now: bool, offer_text: bool) -> guava.Field:
    if open_now:
        return guava.Field(
            key="outcome",
            field_type="multiple_choice",
            choices=[TRANSFER, DONE],
            required=False,
            description=(
                "Never ask the caller for this. They may ask any number of questions: answer "
                "each one and let them lead, without asking whether they have more questions "
                f"afterwards. Record '{TRANSFER}' only when they ask to speak with a person, "
                f"the support center or a representative. Record '{DONE}' only when they say "
                "they are finished, such as 'that's all' or 'goodbye'. Don't offer these as a menu."
            ),
        )

    choices = [VOICEMAIL, DONE]
    wants = f"Record '{VOICEMAIL}' only if they want to leave a message or speak with a person"
    if offer_text:
        choices.insert(1, TEXT_MESSAGE)
        wants += f", and '{TEXT_MESSAGE}' only if they ask for a link by text"
    return guava.Field(
        key="outcome",
        field_type="multiple_choice",
        choices=choices,
        required=False,
        description=(
            "Never ask the caller for this. Our live team isn't available right now. They may "
            "ask any number of questions: answer each one and let them lead, without asking "
            f"whether they have more questions afterwards. {wants}. Record '{DONE}' only when "
            "they say they are finished, such as 'that's all' or 'goodbye'. Don't offer these as a menu."
        ),
    )
