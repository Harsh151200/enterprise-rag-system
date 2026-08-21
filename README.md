# Enterprise RAG System

Enterprise Retrieval-Augmented Generation (RAG) platform with:
- FastAPI backend for query + ingestion APIs
- Streamlit frontend for operator workflows
- PostgreSQL + pgvector storage/retrieval
- Pluggable local/web ingestion pipeline
- Terraform-based GCP deployment (Cloud Run, Cloud SQL, Secret Manager, IAP)

## Project layout

- `app.py` — FastAPI service entrypoint
- `app_ui.py` — Streamlit UI
- `cli.py` — operational CLI (`db-init`, `ingest`, `query`, `status`)
- `components/` — orchestration and embedding pipeline entrypoints
- `ingestion/` — connectors, parsers, deduplication, transformation
- `storage/` — DB access, retrieval, analytics
- `core/config.py` — environment-aware settings
- `infra/` — Terraform infrastructure
- `tests/` — unit/API tests

## Core capabilities

- Hybrid retrieval with citation-oriented responses
- Multi-format ingestion (`.txt`, `.md`, `.html`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.xml`, `.py`, `.json`, `.ini`, `.yaml`, `.yml`)
- Deduplication via content hashes
- Payload guardrails for ingestion safety
- API key protection on all `/api/v1/*` routes

## Prerequisites

- Python 3.11+
- Docker (for local/staging DB or compose stack)
- PostgreSQL with pgvector (or `pgvector/pgvector` Docker image)

## Quick start (local)

### 1) Configure environment
Create `.env.development` from `.env.template` and set:
- `APP_ENV=DEVELOPMENT`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `API_KEY`
- one of `OPENAI_API_KEY` or `GITHUB_TOKEN`

### 2) Start local DB
```bash
docker run \
  --name local-rag-db \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=enterprise_rag_db \
  -p 5433:5432 \
  -d pgvector/pgvector:pg16
```

### 3) Install dependencies
```bash
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

### 4) Initialize schema
```bash
python cli.py db-init
```

### 5) Start backend
```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 6) Start frontend
```bash
#PowerShell
$env:API_KEY="<your_api_key>";streamlit run app_ui.py --server.port 8501
```

## API overview

- `GET /health`
- `GET /api/v1/status` (auth)
- `GET /api/v1/logs` (auth)
- `POST /api/v1/query` (auth)
- `POST /api/v1/ingest` (auth, async background task)

Auth header for protected routes:
```http
X-API-Key: <your_api_key>
```

## CLI usage

```bash
python cli.py db-init
python cli.py status
python cli.py ingest --type local --path data_sandbox/test_inputs --limit 10 --batch-size 50
python cli.py ingest --type web --path https://example.com/docs --limit 20
python cli.py query "What are the model constraints?"
```

## Staging with Docker Compose

```bash
docker-compose --env-file .env.staging -f docker-compose.staging.yml up -d --build
docker exec -it staging-rag-backend python cli.py db-init
```

## Production deployment (GCP)

Infrastructure is managed in `infra/` via Terraform and provisions:
- Cloud Run backend/frontend
- Cloud SQL (private networking)
- Secret Manager secrets + IAM bindings
- Artifact Registry
- HTTPS LB + IAP backend config

Recommended flow:
1. Provision Artifact Registry target first.
2. Build/push backend and frontend images.
3. Run full Terraform apply.

See `/home/runner/work/enterprise-rag-system/enterprise-rag-system/RUNBOOK.md` for detailed operations and current security posture notes.

## Testing

```bash
pytest -q
```

## Notes

- LLM orchestration uses `OPENAI_API_KEY` when present, otherwise falls back to GitHub Models through `GITHUB_TOKEN`.
- Ingestion and parser behavior is implemented in `ingestion/pipeline.py` and `ingestion/connectors.py`.
- Keep secrets out of source and use environment variables / secret managers only.
