# kb-service

Knowledge-base search and answering for the CLA voice agent. Runs on the TTU server next
to its own Postgres (pgvector); `inbound-cla` calls it over HTTPS when a caller asks a
question. Built in phases — what exists so far is listed below.

## Layout

| File | Job |
|---|---|
| `kb_service/settings.py` | Reads and validates configuration from environment variables |
| `kb_service/domain.py` | `KnowledgeDocument` and `Answer`, the types every module shares |
| `kb_service/interfaces.py` | `DocumentSource`, `Embedder`, `VectorIndex`, `Retriever` and `Answerer`, the seams between parts |
| `kb_service/chunker.py` | Splits a document into passages on paragraph boundaries, with overlap |
| `kb_service/embedding.py` | `OpenAIEmbedder`: text to vectors, in batches |
| `kb_service/pgvector_index.py` | `PgVectorIndex`: stores passages and finds the closest to a vector in Postgres |
| `kb_service/sources.py` | `DirectoryDocumentSource`: reads `.md` and `.txt` files from a folder |
| `kb_service/ingest.py` | Keeps the index in step with the documents; also the `ingest` command |
| `kb_service/retrieval.py` | `IndexRetriever`: question to the closest passages |
| `kb_service/wiring.py` | The only place that builds the real OpenAI and Postgres implementations |
| `infra/docker-compose.yml` | Postgres with pgvector for the server, bound to `127.0.0.1:55440` |
| `tests/fakes.py` | In-memory stand-ins so tests need no OpenAI key or database |

## Setup

```bash
cp .env.example .env
uv sync
```

## Tests

```bash
uv run pytest tests/ -q
```

Tests against a real Postgres are skipped unless `KB_TEST_DATABASE_URL` is set; each uses
its own throwaway table.

## Loading documents

```bash
uv run --env-file .env python -m kb_service.ingest path/to/documents --dry-run   # preview
uv run --env-file .env python -m kb_service.ingest path/to/documents
```

Safe to repeat: unchanged documents are skipped and not re-embedded, changed ones are
replaced, and documents no longer in the folder are removed. An empty folder is refused
unless `--allow-empty` is passed, so a wrong path can't wipe the index.
