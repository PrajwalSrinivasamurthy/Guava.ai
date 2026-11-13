# kb-service

Knowledge-base search and answering for the CLA voice agent. Runs on the TTU server next
to its own Postgres (pgvector); `inbound-cla` calls it over HTTPS when a caller asks a
question. Built in phases — what exists so far is listed below.

## Layout

| File | Job |
|---|---|
| `kb_service/settings.py` | Reads and validates configuration from environment variables |
| `kb_service/domain.py` | `KnowledgeDocument` and `Answer`, the types every module shares |
| `kb_service/interfaces.py` | `DocumentSource`, `Retriever` and `Answerer`, the seams between parts |

## Setup

```bash
cp .env.example .env
uv sync
```

## Tests

```bash
uv run pytest tests/ -q
```
