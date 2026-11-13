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
| `kb_service/generation.py` | `OpenAIGenerator`: writes a short spoken answer from the passages |
| `kb_service/answering.py` | `RagAnswerer`: search, then generate; turns the model's `NO_ANSWER` into `found=false` |
| `kb_service/auth.py` | Checks the bearer key against stored SHA-256 hashes (several allowed, for rotation) |
| `kb_service/ratelimit.py` | Caps requests per minute so a leaked key can't run up the OpenAI bill |
| `kb_service/keys.py` | `python -m kb_service.keys --key-file F` makes a key, writes it privately, prints only its hash |
| `kb_service/app.py` | The HTTP interface: `POST /answer` and `GET /health`; question text is never logged |
| `kb_service/server.py` | Entry point that builds everything from the environment |
| `kb_service/wiring.py` | The only place that builds the real OpenAI and Postgres implementations |
| `Dockerfile` | Builds the service image |
| `infra/docker-compose.yml` | The database (`127.0.0.1:55440`) and the service (`127.0.0.1:8120`) for the server |
| `infra/service.env.example` | Names the settings the service container needs |
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

## Running the service

On the server, from `~/cla-kb/` (see `infra/docker-compose.yml` for the file layout):

```bash
docker compose --env-file ~/cla-kb/.env -f ~/cla-kb/kb-service/infra/docker-compose.yml up -d --build
```

The service listens on `127.0.0.1:8120` only; nginx forwards a path to it. To ask a question:

```bash
curl -s -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"question": "Do I need a textbook?"}' http://127.0.0.1:8120/answer
```
