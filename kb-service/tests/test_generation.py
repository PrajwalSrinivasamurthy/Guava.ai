from types import SimpleNamespace

from kb_service.generation import OpenAIGenerator


class _FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_the_prompt_carries_the_organization_the_excerpts_and_the_question():
    client = _FakeClient("  Use the bookstore.  ")
    generator = OpenAIGenerator(client, "gpt-test", "Career Learning Academy", 150)

    reply = generator.generate("Where are books?", ["Books are sold at the bookstore.", "Digital copies exist."])

    assert reply == "Use the bookstore."
    call = client.calls[0]
    assert call["model"] == "gpt-test" and call["max_completion_tokens"] == 150
    system, user = (message["content"] for message in call["messages"])
    assert "Career Learning Academy" in system and "NO_ANSWER" in system
    assert "clearly imply" in system and "Never guess" in system
    assert "[1] Books are sold at the bookstore." in user and "[2] Digital copies exist." in user
    assert user.endswith("Where are books?")


def test_an_empty_model_reply_becomes_an_empty_string():
    assert OpenAIGenerator(_FakeClient(None), "m", "Org", 100).generate("q", ["p"]) == ""
