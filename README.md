# Production RAG Agent

A portfolio project showing two sides of retrieval-augmented generation: a deployable
document-grounded API and a separate local-learning project.

## Projects

### Production RAG API

[`production-api/`](./production-api/) is a FastAPI service using Gemini for embeddings
and answer generation, PostgreSQL/pgvector for persistent semantic retrieval, and
overlapping document chunks. It supports PDF, Markdown, and text ingestion, cited
answers, a fallback model, bearer-token protection for chat, rate limiting, structured
logs, and Docker deployment.

Start with the [production API guide](./production-api/README.md) for configuration,
database setup, ingestion, local development, tests, and deployment.

### Local RAG learning project

[`learning/simple-local-rag/`](./learning/simple-local-rag/) is a Git submodule pointing
to the upstream [simple-local-rag tutorial](https://github.com/mrdbourke/simple-local-rag).
It is kept separate so the original tutorial and its license/attribution stay with its
maintainer instead of being copied into this repository.

Clone the project with the learning submodule:

```powershell
git clone --recurse-submodules https://github.com/abhinaya286/production-rag-agent.git
```

If you already cloned it:

```powershell
git submodule update --init --recursive
```

## Architecture

```text
Documents (PDF / Markdown / TXT)
          |
          v
  text extraction + overlapping chunking
          |
          v
 Gemini embeddings -> PostgreSQL / pgvector
                              |
Question -> embedding -> semantic retrieval
                              |
                              v
                 Gemini answer + citations
                              |
                              v
                     FastAPI /chat
```

The API uses a single shared knowledge-base collection; it is not a multi-tenant
service. Request metrics, rate limiting, and response cache are process-local. Read
the deployment notes before exposing the service to the public internet.

## Quick start

Requirements: Python 3.13+, `uv`, a Gemini API key, and PostgreSQL with the pgvector
extension enabled. See [production-api/.env.example](./production-api/.env.example)
for configuration keys; create a local `.env` and never commit credentials.

From `production-api/`:

```powershell
Copy-Item .env.example .env
# Add GEMINI_API_KEY and DATABASE_URL (or SUPABASE_* settings) to .env.
uv sync
uv run production-api-ingest .\knowledge_base
uv run production-api
```

Interactive API docs: <http://localhost:8000/docs>.

## Quality checks

From `production-api/`:

```powershell
uv run pytest
uv build
```

Tests use mocked providers and do not need live Gemini credentials or a database.
Verify ingestion and retrieval against a development database before deployment.

## Security and operations

- Never commit `.env`, API tokens, database passwords, uploaded documents, or local
  virtual environments.
- Rotate credentials immediately if they have ever been exposed or committed.
- Configure `APP_ENV=production` and a strong `API_ACCESS_TOKEN`; `/chat` requires a
  bearer token in production.
- Put the API behind HTTPS and gateway/network access controls. Health, metrics, and
  cache-stat endpoints do not have built-in authentication.
- Review data retention and provider data handling before embedding private documents.

## Repository layout

```text
production-rag-agent/
├── production-api/       # Packaged API, tests, container and ingestion CLI
└── learning/
    └── simple-local-rag/ # Upstream local-RAG tutorial Git submodule
```
