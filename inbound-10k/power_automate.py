import logging
import time

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

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 1  # doubles each retry: 1s, 2s


def send_lead(call, fields: dict) -> bool:
    """Push a captured enrollment lead to the legacy Power Automate flow. Retries up to
    _MAX_ATTEMPTS times with exponential backoff on connection errors/timeouts and 5xx
    responses — a 4xx means the flow rejected the request itself (bad payload/auth), so
    retrying it verbatim won't help and only delays ending the call. Returns False (never
    raises) if every attempt fails — the caller has already been told a team member will
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

    logger.info("Power Automate lead push request body: %s", body)

    def _wait_before_retry(attempt: int, exc: Exception) -> None:
        backoff = _BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
        logger.warning(
            "Power Automate lead push failed (attempt %d/%d): %s — retrying in %ss",
            attempt, _MAX_ATTEMPTS, exc, backoff,
        )
        time.sleep(backoff)

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = httpx.post(settings.TENK_POWER_AUTOMATE_URL, json=body, headers=headers, timeout=10)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_ATTEMPTS:
                _wait_before_retry(attempt, exc)
            continue

        logger.info(
            "Power Automate lead push response (attempt %d/%d): status=%s body=%s",
            attempt, _MAX_ATTEMPTS, response.status_code, response.text,
        )

        try:
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                logger.warning(
                    "Power Automate lead push rejected (status %s) — not retrying: %s",
                    exc.response.status_code, exc,
                )
                return False
            last_exc = exc

        if attempt < _MAX_ATTEMPTS:
            _wait_before_retry(attempt, last_exc)

    logger.warning("Power Automate lead push failed after %d attempts: %s", _MAX_ATTEMPTS, last_exc)
    return False
