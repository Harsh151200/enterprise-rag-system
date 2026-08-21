# Enterprise RAG Platform — Operational Runbook

**Repository:** `enterprise-rag-system`  
**Runtime stack:** FastAPI API + Streamlit UI + PostgreSQL/pgvector + Cloud Run + Terraform

---

## 1) System architecture (current)

- **Backend API:** `app.py` (FastAPI)
- **Frontend UI:** `app_ui.py` (Streamlit)
- **Ingestion/ETL:** `components/embedder.py`, `ingestion/*`
- **Retrieval + orchestration:** `storage/retriever.py`, `components/orchestrator.py`
- **Database:** PostgreSQL with pgvector
- **Infrastructure as code:** `infra/main.tf`

### LLM inference routing (current behavior)
`components/orchestrator.py` selects credentials in this order:
1. `OPENAI_API_KEY` (direct OpenAI API)
2. `GITHUB_TOKEN` (GitHub Models endpoint: `https://models.github.ai/inference`)

If neither is present, query orchestration returns a credentials error response.

---

## 2) Environment contract

`core/config.py` controls env selection via `APP_ENV`:
- `DEVELOPMENT` → `.env.development`
- `STAGING` → `.env.staging`
- `PRODUCTION` → `.env.production`

### Key runtime variables
- `APP_ENV`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `API_KEY` (required for `/api/v1/*`)
- `OPENAI_API_KEY` and/or `GITHUB_TOKEN`

`SQLALCHEMY_DATABASE_URI` is auto-assembled when not explicitly provided.

---

## 3) API operations

### Health and status
- `GET /health` (no API key)
- `GET /api/v1/status` (requires `X-API-Key`)
- `GET /api/v1/logs` (requires `X-API-Key`)

### Query and ingestion
- `POST /api/v1/query` (requires `X-API-Key`)
- `POST /api/v1/ingest` (requires `X-API-Key`, ingestion runs in background task)

### Auth behavior
- Missing/invalid API key on `/api/v1/*` returns `401`.

---

## 4) Local development runbook

### Step 1 — Prepare environment file
Create `.env.development` from `.env.template` and set at minimum:
- `APP_ENV=DEVELOPMENT`
- DB variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)
- `API_KEY`
- one of `OPENAI_API_KEY` or `GITHUB_TOKEN`

### Step 2 — Start local PostgreSQL/pgvector
Example:
```bash
docker run \
  --name local-rag-db \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=enterprise_rag_db \
  -p 5433:5432 \
  -d pgvector/pgvector:pg16
```

### Step 3 — Install dependencies
```bash
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

### Step 4 — Initialize schema
```bash
python cli.py db-init
```

### Step 5 — Run backend
```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Step 6 — Run frontend
```bash
streamlit run app_ui.py --server.port 8501
```

---

## 5) Staging (Docker Compose)

Use `.env.staging` and run:
```bash
docker-compose --env-file .env.staging -f docker-compose.staging.yml up -d --build
```

Then initialize schema in backend container:
```bash
docker exec -it staging-rag-backend python cli.py db-init
```

---

## 6) Production deployment (Terraform + Cloud Run)

### Step 1 — Bootstrap Artifact Registry
```bash
cd infra
terraform apply -target=google_artifact_registry_repository.rag_repository -var-file="terraform.tfvars"
```

### Step 2 — Build and push images
Build and push backend/frontend images to:
- `${region}-docker.pkg.dev/${project_id}/enterprise-rag-repo/api-service:<tag>`
- `${region}-docker.pkg.dev/${project_id}/enterprise-rag-repo/frontend-ui:<tag>`

### Step 3 — Full infra apply
```bash
cd infra
terraform apply -var-file="terraform.tfvars"
```

---

## 7) Security posture (as currently configured)

### Implemented controls
- API routes protected by `X-API-Key` middleware.
- Secrets injected through Google Secret Manager.
- Cloud SQL is configured for private networking (`ipv4_enabled = false`).
- IAP is configured on the external HTTPS load balancer backend service.

### Important current exposure
In `infra/main.tf`, Cloud Run invoker IAM for both frontend and backend is currently bound to:
- `roles/run.invoker` with `members = ["allUsers"]`

This is a **public invoker** posture at Cloud Run IAM level and does **not** represent strict private-invoker enforcement.

---

## 8) CLI operations

```bash
python cli.py db-init
python cli.py status
python cli.py ingest --type local --path data_sandbox/test_inputs --limit 10 --batch-size 50
python cli.py query "What is RandomForestClassifier?"
```

---

## 9) Troubleshooting

- **401 on `/api/v1/*`:** validate `X-API-Key` header and `API_KEY` env value.
- **DB connection errors:** confirm host/port for the active environment and run `python cli.py db-init`.
- **LLM errors:** ensure one of `OPENAI_API_KEY` or `GITHUB_TOKEN` is set.
- **Ingestion returns little/no data:** verify source path/URL and extension/MIME guardrails in `ingestion/pipeline.py` and `ingestion/connectors.py`.
