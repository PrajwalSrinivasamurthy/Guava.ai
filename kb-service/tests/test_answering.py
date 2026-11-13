import pytest

from kb_service.answering import RagAnswerer
from kb_service.domain import Answer


class _Retriever:
    def __init__(self, passages):
        self.passages = passages
        self.calls = []

    def search(self, question, limit):
        self.calls.append((question, limit))
        return self.passages


class _Generator:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate(self, question, passages):
        self.calls.append((question, passages))
        return self.reply


def test_an_answer_is_returned_with_found_set():
    retriever, generator = _Retriever(["Books come from the bookstore."]), _Generator("  Buy them at the bookstore. ")

    result = RagAnswerer(retriever, generator, 3).answer("Where do I get books?")

    assert result == Answer(found=True, text="Buy them at the bookstore.")
    assert retriever.calls == [("Where do I get books?", 3)]
    assert generator.calls == [("Where do I get books?", ["Books come from the bookstore."])]


def test_no_passages_means_not_found_and_the_model_is_not_called():
    generator = _Generator("anything")

    result = RagAnswerer(_Retriever([]), generator, 3).answer("Unrelated?")

    assert result == Answer.not_found()
    assert generator.calls == []


@pytest.mark.parametrize("reply", ["NO_ANSWER", " no_answer. ", "No_Answer!", "", "   "])
def test_the_no_answer_marker_and_empty_replies_mean_not_found(reply):
    assert RagAnswerer(_Retriever(["x"]), _Generator(reply), 3).answer("q") == Answer.not_found()


def test_an_answer_that_merely_contains_the_marker_text_is_kept():
    reply = "There is no answer fee for that."

    assert RagAnswerer(_Retriever(["x"]), _Generator(reply), 3).answer("q").found is True


def test_stage_timings_are_logged_without_the_question(caplog):
    import logging

    with caplog.at_level(logging.INFO, logger="kb_service.answering"):
        RagAnswerer(_Retriever(["x"]), _Generator("An answer."), 3).answer("my private question 8675309")

    assert "search_ms=" in caplog.text and "generate_ms=" in caplog.text
    assert "8675309" not in caplog.text
