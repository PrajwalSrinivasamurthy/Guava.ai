import pytest

from kb_service.settings import ConfigError, Settings

_REQUIRED = {"OPENAI_API_KEY": "sk-secret", "DATABASE_URL": "postgresql://user:pw@localhost/kb"}


def test_defaults_apply_when_only_required_values_are_set():
    settings = Settings.from_env(_REQUIRED)

    assert settings.chat_model == "gpt-4o-mini"
    assert settings.chunk_size == 1200
    assert settings.retrieval_limit == 4


def test_every_missing_required_value_is_reported_at_once():
    with pytest.raises(ConfigError) as error:
        Settings.from_env({})

    assert "OPENAI_API_KEY" in str(error.value)
    assert "DATABASE_URL" in str(error.value)


def test_blank_values_count_as_missing():
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        Settings.from_env({**_REQUIRED, "OPENAI_API_KEY": "   "})


def test_overrides_are_parsed():
    settings = Settings.from_env({
        **_REQUIRED,
        "OPENAI_CHAT_MODEL": "gpt-4o",
        "KB_CHUNK_SIZE": "800",
        "KB_CHUNK_OVERLAP": "100",
        "KB_RETRIEVAL_LIMIT": "6",
        "OPENAI_TIMEOUT_SECONDS": "5.5",
    })

    assert settings.chat_model == "gpt-4o"
    assert (settings.chunk_size, settings.chunk_overlap) == (800, 100)
    assert settings.retrieval_limit == 6
    assert settings.openai_timeout_seconds == 5.5


@pytest.mark.parametrize("raw", ["many", "0", "-3"])
def test_invalid_numbers_name_the_variable(raw):
    with pytest.raises(ConfigError, match="KB_RETRIEVAL_LIMIT"):
        Settings.from_env({**_REQUIRED, "KB_RETRIEVAL_LIMIT": raw})


def test_overlap_must_be_smaller_than_the_chunk_size():
    with pytest.raises(ConfigError, match="KB_CHUNK_OVERLAP"):
        Settings.from_env({**_REQUIRED, "KB_CHUNK_SIZE": "100", "KB_CHUNK_OVERLAP": "100"})


def test_embedding_dimensions_default_and_limit():
    assert Settings.from_env(_REQUIRED).embedding_dimensions == 1536

    with pytest.raises(ConfigError, match="OPENAI_EMBEDDING_DIMENSIONS"):
        Settings.from_env({**_REQUIRED, "OPENAI_EMBEDDING_DIMENSIONS": "3072"})


def test_secrets_never_appear_in_repr():
    shown = repr(Settings.from_env(_REQUIRED))

    assert "sk-secret" not in shown
    assert "pw@localhost" not in shown
