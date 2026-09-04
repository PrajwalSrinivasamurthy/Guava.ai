import logging
import os

import guava

import settings

logger = logging.getLogger(__name__)


def send_link(to_number: str | None, url: str, body_prefix: str) -> bool:
    """Text `to_number` a link. Returns False (never raises) on any failure — including a
    not-yet-configured URL — so the caller can degrade to a spoken apology instead of claiming
    a delivery that did not happen."""
    if not to_number or not url or not settings.SMS_ENABLED:
        logger.warning(
            "Cannot send text link (to_number=%r, url_configured=%s, SMS_ENABLED=%s)",
            to_number, bool(url), settings.SMS_ENABLED,
        )
        return False
    try:
        guava.Client().send_sms(os.environ["GUAVA_AGENT_NUMBER"], to_number, f"{body_prefix} {url}")
    except Exception as exc:
        # check_response (guava.client) embeds status/reason/body in httpx.HTTPStatusError's
        # own message — str(exc), not just the exception type, carries the actual reason.
        logger.warning("Text link send failed (%s): %s", type(exc).__name__, exc)
        return False
    return True
