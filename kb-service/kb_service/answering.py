"""Answering a question from the knowledge base."""

import re

from kb_service.domain import Answer
from kb_service.interfaces import Generator, Retriever

# The generator is told to reply with exactly this when the passages don't contain the
# answer. The service turns it into Answer.not_found(), and the caller (the voice agent)
# decides what to say, so the wording of "I don't know" never depends on the model.
NO_ANSWER = "NO_ANSWER"


class RagAnswerer:
    def __init__(self, retriever: Retriever, generator: Generator, retrieval_limit: int):
        self._retriever = retriever
        self._generator = generator
        self._retrieval_limit = retrieval_limit

    def answer(self, question: str) -> Answer:
        passages = self._retriever.search(question, self._retrieval_limit)
        if not passages:
            return Answer.not_found()
        text = self._generator.generate(question, passages).strip()
        if not text or _is_no_answer(text):
            return Answer.not_found()
        return Answer(found=True, text=text)


def _is_no_answer(text: str) -> bool:
    return re.sub(r"[^a-z_]", "", text.lower()) == NO_ANSWER.lower()
