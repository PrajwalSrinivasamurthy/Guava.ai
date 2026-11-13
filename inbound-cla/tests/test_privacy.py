import logging


def test_the_sdk_line_with_the_callers_question_loses_the_words(app, caplog):
    with caplog.at_level(logging.INFO, logger="guava.agent"):
        logging.getLogger("guava.agent").info("Received a question from agent: %s", "my private question 8675309")

    assert "8675309" not in caplog.text
    assert "Received a question from agent: [redacted]" in caplog.text


def test_the_no_handler_warning_is_redacted_too(app, caplog):
    with caplog.at_level(logging.WARNING, logger="guava.agent"):
        logging.getLogger("guava.agent").warning(
            "Received question but no on_question handler is registered: %s", "my private question 8675309"
        )

    assert "8675309" not in caplog.text


def test_other_sdk_log_lines_are_left_alone(app, caplog):
    with caplog.at_level(logging.INFO, logger="guava.agent"):
        logging.getLogger("guava.agent").info("Started listing on phone number %s.", "+18065533554")

    assert "Started listing on phone number +18065533554." in caplog.text


def test_installing_twice_adds_only_one_filter(app):
    import privacy

    privacy.install()
    privacy.install()

    assert len([f for f in logging.getLogger("guava.agent").filters if type(f).__name__ == "_DropCallerWords"]) == 1
