import sys

from kb_service import wiring
from kb_service.settings import Settings

_SETTINGS = Settings.from_env({"OPENAI_API_KEY": "sk-test", "DATABASE_URL": "postgresql://x"})


def test_the_openai_client_holds_idle_connections_open(monkeypatch):
    # The service image has no httpx of its own (openai bundles one); block it here so a
    # direct import fails this test instead of crashing the service at startup.
    monkeypatch.setitem(sys.modules, "httpx", None)

    client = wiring.build_openai_client(_SETTINGS, max_retries=1)

    assert client._client._transport._pool._keepalive_expiry == 300.0
