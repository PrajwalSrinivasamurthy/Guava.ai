import logging

import httpx

import settings

logger = logging.getLogger(__name__)

# Maps this Power Automate flow's expected JSON keys to our call-field keys — carried over
# from the legacy connector script so the flow itself doesn't need to change. The legacy
# script also sent a NotIntAnswer (a reason-for-declining field); this rebuild doesn't
# collect that, so it's simply never included below.
_FIELD_MAP = {
    "MarketingSource": "marketing_source",
    "EnrollmentInterest": "enrollment_interested",
    "CallerFirstName": "first_name",
    "CallerLastName": "last_name",
    "Email": "email",
    "CollectedNumber": "phone_number",
    "ContactPref": "contact_preference",
    "CollegeCredits": "college_credits",
    "Location": "location",
    "WillingToTravel": "willing_to_travel",
}


def send_lead(call, fields: dict) -> bool:
    """Push a captured enrollment lead to the legacy Power Automate flow. Returns False
    (never raises) on any failure — the caller has already been told a team member will
    follow up, so a failed push here shouldn't block ending the call."""
    if not settings.TENK_POWER_AUTOMATE_URL:
        logger.warning("Cannot push enrollment lead: TENK_POWER_AUTOMATE_URL not configured")
        return False

    body = {"PhoneNumber": getattr(call.call_info, "from_number", None)}
    for pa_key, field_key in _FIELD_MAP.items():
        value = fields.get(field_key)
        if value is not None:
            body[pa_key] = str(value) if pa_key == "CollegeCredits" else value

    headers = {"Content-Type": "application/json"}
    if settings.TENK_POWER_AUTOMATE_API_KEY:
        headers["x-api-key"] = settings.TENK_POWER_AUTOMATE_API_KEY

    try:
        response = httpx.post(settings.TENK_POWER_AUTOMATE_URL, json=body, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Power Automate lead push failed (%s): %s", type(exc).__name__, exc)
        return False
    return True
