from types import SimpleNamespace

from kb_service.embedding import OpenAIEmbedder


class _FakeClient:
    """Mimics client.embeddings.create, returning items out of order like a real batch might."""

    def __init__(self):
        self.calls = []
        self.embeddings = self

    def create(self, *, model, input, dimensions):
        self.calls.append({"model": model, "input": list(input), "dimensions": dimensions})
        items = [SimpleNamespace(index=i, embedding=[float(len(text))]) for i, text in enumerate(input)]
        return SimpleNamespace(data=list(reversed(items)))


def test_vectors_come_back_in_input_order():
    embedder = OpenAIEmbedder(_FakeClient(), "m", 1, batch_size=10)

    assert embedder.embed(["a", "bb", "ccc"]) == [[1.0], [2.0], [3.0]]


def test_texts_are_sent_in_batches_with_the_configured_model_and_size():
    client = _FakeClient()
    embedder = OpenAIEmbedder(client, "text-embedding-3-small", 1536, batch_size=2)

    result = embedder.embed(["a", "bb", "ccc", "dddd", "eeeee"])

    assert [call["input"] for call in client.calls] == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert all(call["model"] == "text-embedding-3-small" and call["dimensions"] == 1536 for call in client.calls)
    assert result == [[1.0], [2.0], [3.0], [4.0], [5.0]]


def test_no_texts_makes_no_request():
    client = _FakeClient()

    assert OpenAIEmbedder(client, "m", 1).embed([]) == []
    assert client.calls == []
