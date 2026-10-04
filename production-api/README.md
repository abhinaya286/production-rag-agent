# Production RAG API

FastAPI service for document-grounded question answering. It ingests PDF, Markdown,
and UTF-8 text files, chunks them with overlap, stores Gemini embeddings in PostgreSQL
pgvector, retrieves relevant chunks, and asks Gemini to answer only from retrieved
context. Responses include source filenames and PDF page numbers where available.

This package uses the existing Supabase/PostgreSQL direction in the repository. It is
a single-knowledge-base service, not a multi-tenant system. Put it behind HTTPS and an
appropriate gateway before exposing it publicly.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL with the pgvector extension enabled (Supabase PostgreSQL works)
- A Google Gemini API key

In Supabase, enable the `vector` extension in the database before starting the service:

```sql
create extension if not exists vector;
```

The service does not create or drop database extensions automatically. The pgvector
tables and collection are created as documents are first ingested.

## Configure

From this directory, create a local environment file from the template:

```powershell
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` and either `DATABASE_URL` or the `SUPABASE_*` connection fields.
Use a URL-encoded password if supplying a `DATABASE_URL`. Keep `.env` out of Git.
In production, set `APP_ENV=production` and provide a long, random `API_ACCESS_TOKEN`;
the `/chat` endpoint then requires it as a bearer token.

The deployment process also sends document chunks and questions to Google Gemini.
Only ingest data you are authorized to process with that provider.

## Install and ingest

```powershell
uv sync
uv run production-api-ingest .\knowledge_base
```

The ingestion command accepts one supported file or recursively scans a directory for
`.pdf`, `.md`, and `.txt` files. It uses 1,000-character chunks with 150-character
overlap by default. Tune `CHUNK_SIZE`, `CHUNK_OVERLAP`, and `RETRIEVAL_K` in `.env` if
needed. Re-running ingestion adds new records; it does not delete or replace prior
documents. Use a new collection name for a clean re-index, or manage cleanup through
your database operations.

## Run locally

```powershell
uv run production-api
```

The interactive API docs are at <http://localhost:8000/docs>. The application checks
the required API/database settings on startup. Database connectivity is exercised by
ingestion or the first question, so successful startup alone does not confirm that
PostgreSQL is reachable.

Example request (PowerShell):

```powershell
$headers = @{
  Authorization = "Bearer $env:API_ACCESS_TOKEN"
  "Content-Type" = "application/json"
}
$body = @{
  message = "What does the knowledge base say about the topic?"
  thread_id = "demo"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/chat -Headers $headers -Body $body
```

In development, bearer authentication is optional unless `API_ACCESS_TOKEN` is set.
In production, it is mandatory. `/health`, `/metrics`, and `/cache/stats` are intended
for a trusted network or an authenticated gateway and should not be exposed publicly
without additional access controls.

## Docker

After configuring `.env`, build and run the API:

```powershell
docker compose up --build -d
docker compose logs -f agent-api
```

The image runs as a non-root user and uses Python 3.13 to match the package's
`requires-python`. The vector collection lives in the configured PostgreSQL database,
not in the container filesystem.

## Endpoints

- `POST /chat` — retrieve document context and generate a grounded answer.
- `GET /health` — application component readiness.
- `GET /metrics` — in-process request, latency, token-estimate, and cache metrics.
- `GET /cache/stats` — in-memory cache statistics.

Example `POST /chat` body:

```json
{
  "message": "What is covered in the indexed documents?",
  "thread_id": "demo"
}
```

The response includes `response`, `model_used`, `cached`, `sources`, and
`processing_time_ms`. This service does not preserve conversational history between
requests; each request is answered from retrieved documents and its current question.

## Before production

- Rotate any credentials that have previously been committed or shared, then put
  replacements in a secret manager or deployment environment.
- Use TLS, restrict network access to PostgreSQL, and enforce authentication and
  authorization at the gateway; the API token is a simple single-service credential,
  not user identity or tenant isolation.
- Back up the pgvector database, monitor provider/database errors, and load-test with
  the expected document volume and request concurrency.
- Review PII policies, document retention, provider data handling, and whether the
  in-memory cache is appropriate for the data.
- `/metrics` and health/cache endpoints have no built-in authentication; keep them
  behind trusted network controls.
- The cache, rate limiter, and metrics are process-local and reset on restart. For
  multiple workers or replicas, use gateway-level rate limiting and externalized
  observability/caching rather than relying on these in-memory counters.