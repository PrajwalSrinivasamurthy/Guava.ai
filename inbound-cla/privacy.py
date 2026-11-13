"""Keeps callers' words out of the logs.

The Guava SDK logs every question it passes to on_question, word for word, at INFO level.
This filter keeps the line but drops the words.
"""

import logging

_REDACTED = (
    "Received a question from agent",
    "Received question but no on_question handler",
)


class _DropCallerWords(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        template = str(record.msg)
        if template.startswith(_REDACTED):
            record.msg = template.split(":", 1)[0] + ": [redacted]"
            record.args = ()
        return True


def install() -> None:
    logger = logging.getLogger("guava.agent")
    if not any(isinstance(existing, _DropCallerWords) for existing in logger.filters):
        logger.addFilter(_DropCallerWords())
