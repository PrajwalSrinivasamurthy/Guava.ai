import stat

from kb_service.auth import ApiKeyVerifier, hash_key
from kb_service.keys import main


def test_the_right_key_is_accepted_and_others_are_not():
    verifier = ApiKeyVerifier((hash_key("secret-one"),))

    assert verifier.verify("secret-one") is True
    assert verifier.verify("secret-two") is False
    assert verifier.verify("") is False
    assert verifier.verify(None) is False


def test_any_of_several_active_keys_is_accepted_for_rotation():
    verifier = ApiKeyVerifier((hash_key("old"), hash_key("new")))

    assert verifier.verify("old") and verifier.verify("new")
    assert not verifier.verify("older")


def test_no_configured_keys_accepts_nothing():
    assert ApiKeyVerifier(()).verify("anything") is False


def test_the_key_command_writes_the_key_privately_and_prints_only_its_hash(tmp_path, capsys):
    key_file = tmp_path / "key.txt"

    assert main(["--key-file", str(key_file)]) == 0

    key = key_file.read_text().strip()
    output = capsys.readouterr().out
    assert key not in output
    assert hash_key(key) in output
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600


def test_the_key_command_never_overwrites_an_existing_file(tmp_path, capsys):
    key_file = tmp_path / "key.txt"
    key_file.write_text("keep me")

    assert main(["--key-file", str(key_file)]) == 1
    assert key_file.read_text() == "keep me"
