# Enterprise RAG Platform — Operational Runbook

**Runtime:** FastAPI + Streamlit + PostgreSQL/pgvector  
**Deploy:** Docker Compose (staging) · Terraform + Cloud Run (production)

Product context and architecture live in [README.md](README.md). This document is how to configure, run, ingest, query, deploy, and debug.

---

## 1) Prerequisites

- Python **3.11+**
- Docker (local DB or Compose stack)
- For production: `gcloud`, Terraform, a GCP project with billing, and permission to enable the APIs listed in `infra/main.tf`

---

## 2) Environment contract

`core/config.py` selects a settings class from `APP_ENV` (case-insensitive, default `DEVELOPMENT`):

| `APP_ENV` | Env file | Notes |
|---|---|---|
| `DEVELOPMENT` | `.env.development` | `EMBEDDING_MODE=LOCAL` (provider still loads local Nomic) |
| `STAGING` | `.env.staging` | Profile default `EMBEDDING_MODE=CLOUD` |
| `PRODUCTION` | `.env.production` | Same |

Copy `.env.template` to the file for your environment. **Do not commit secrets.**

### Required / important variables

| Variable | Purpose |
|---|---|
| `APP_ENV` | Profile selection |
| `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` | Postgres. `DB_PASSWORD` is required (fail-fast). |
| `SQLALCHEMY_DATABASE_URI` | Optional override; otherwise assembled with URL-encoded password |
| `API_KEY` | Must match `X-API-Key` on `/api/v1/*`. Streamlit reads this too. |
| `OPENAI_API_KEY` | Preferred LLM path |
| `GITHUB_TOKEN` | Fallback: GitHub Models at `https://models.github.ai/inference` |
| `HF_TOKEN` | Optional Hugging Face (template only; not required for the default embedding model) |
| `RAW_DATA_DIR` | Dedup hash ledger directory (default `data_sandbox/`) |
| `BACKEND_API_URL` | Streamlit → API (default `http://127.0.0.1:8000`; Compose sets `http://backend-api:8000`) |
| `PORT` | Cloud Run / containers: Uvicorn and Streamlit honor `${PORT:-8000}` / `${PORT:-8501}` |

LLM routing: **OpenAI key wins**. If only `GITHUB_TOKEN` is set, the orchestrator uses GitHub Models. If neither is set, `/api/v1/query` returns a credentials error in the answer field (HTTP still 200 unless another exception occurs).

---

## 3) API contract

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/health` | No | `{ "status": "healthy", "environment": ... }` |
| `GET` | `/api/v1/status` | `X-API-Key` | Chunk totals and format distribution |
| `GET` | `/api/v1/logs` | `X-API-Key` | Last 10 `pipeline_runs` |
| `POST` | `/api/v1/query` | `X-API-Key` | Body: `{ "question": "..." }` |
| `POST` | `/api/v1/ingest` | `X-API-Key` | **202**; ETL in FastAPI `BackgroundTasks`. Body: `source_type` (`local` \| `web`), `target_path`, optional `limit`, `batch_size` (default 50) |

Invalid or missing key on `/api/v1/*` → **401**.

### Example calls

```bash
curl -s http://127.0.0.1:8000/health

curl -s -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/v1/status

curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is RandomForestClassifier?"}' \
  http://127.0.0.1:8000/api/v1/query

curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"local","target_path":"data_sandbox/test_inputs","limit":10,"batch_size":50}' \
  http://127.0.0.1:8000/api/v1/ingest
```

Web ingest: `source_type` `web`, `target_path` a seed URL. The crawler is locked to **scikit-learn.org** and paths containing **`/stable/`** in code (`components/embedder.py`). Other hosts will not enqueue links.

---

## 4) Local development

### Step 1 — Env file

Create `.env.development` from `.env.template`. Set at least:

- `APP_ENV=DEVELOPMENT`
- DB fields (if the DB is mapped to host **5433**, set `DB_PORT=5433`)
- `API_KEY`
- `OPENAI_API_KEY` and/or `GITHUB_TOKEN`

### Step 2 — PostgreSQL with pgvector

```bash
docker run \
  --name local-rag-db \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=enterprise_rag_db \
  -p 5433:5432 \
  -d pgvector/pgvector:pg16
```

Point `DB_HOST=127.0.0.1` and `DB_PORT=5433` if you use this mapping.

### Step 3 — Dependencies

```bash
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

### Step 4 — Schema

```bash
python cli.py db-init
```

Idempotent: `vector` extension, `pipeline_status_enum`, `enterprise_documents` (HNSW + GIN), `pipeline_runs`.

### Step 5 — Backend

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### Step 6 — Frontend

PowerShell:

```powershell
$env:API_KEY="<your_api_key>"
python -m streamlit run app_ui.py --server.port 8501
```

bash:

```bash
API_KEY="<your_api_key>" python -m streamlit run app_ui.py --server.port 8501
```

UI: `http://127.0.0.1:8501` — **Hybrid Chat Search** and **Ingestion Command Center**. Backend must be up; the UI calls `/health` with a 2s timeout and stops if it cannot connect.

---

## 5) CLI

Run from the repo root with the same env as the backend.

```bash
python cli.py db-init
python cli.py status
python cli.py ingest --type local --path data_sandbox/test_inputs --limit 10 --batch-size 50
python cli.py ingest --type web --path https://scikit-learn.org/stable/ --limit 20
python cli.py query "What is RandomForestClassifier?"
```

| Flag | Meaning |
|---|---|
| `--type` | `local` or `web` (required for ingest) |
| `--path` | Directory or seed URL |
| `--limit` | Max **new** local files processed, or crawler `max_pages` (web default 50 if omitted) |
| `--batch-size` | Embedding buffer before a vector load (default 50) |

CLI ingest is **synchronous** (unlike the API 202 path).

---

## 6) Staging (Docker Compose)

Requires `.env.staging` with DB credentials that match the Compose `POSTGRES_*` mapping.

```bash
docker-compose --env-file .env.staging -f docker-compose.staging.yml up -d --build
docker exec -it staging-rag-backend python cli.py db-init
```

| Service | Host ports | Notes |
|---|---|---|
| `staging-db` | `5434:5432` | Volume `staging_db_data`; healthcheck `pg_isready` |
| `backend-api` | `8000:8000` | `DB_HOST=staging-db`, `APP_ENV=STAGING`; mounts `./data_sandbox` |
| `frontend-ui` | `8501:8501` | `BACKEND_API_URL=http://backend-api:8000` |

First backend request may be slow while the embedding model lazy-loads (weights are baked into the image).

---

## 7) Retrieval evaluation and latency benchmarking

`evaluation_scripts/` validates the hybrid retrieval design against real data instead of assuming it, and builds a topic-scoped test corpus without a full-site crawl. Run these against staging (`docker exec -it staging-rag-backend ...`) for numbers that reflect real infra — a local Docker Postgres on your laptop is fine for iterating on the scripts themselves, not for reporting results.

### Scoped ingestion

The web crawler in `ingestion/connectors.py` follows every `<a href>` on every page it fetches — nav and sidebar included — and `path_filter` is a single substring (hardcoded to `/stable/` in `components/embedder.py`), not topic-aware. Seeding it at one topic page does not keep the crawl on-topic past the first hop. `evaluation_scripts/ingest_topic_subset.py` sidesteps this with no code changes: it calls the ingestion pipeline once per URL with `max_resources=1`, and the crawler's `while queue and len(visited_urls) < max_pages` loop fetches exactly that page and stops before following anything it links to.

```bash
python evaluation_scripts/ingest_topic_subset.py --urls-file evaluation_scripts/topic_urls_supervised_learning.json
```

Each URL becomes its own `pipeline_runs` audit row — expected, one run per page, not a bug.

### Retrieval relevance (Recall@K / MRR)

`evaluation_scripts/eval_retrieval_relevance.py` runs a labeled question set (`{"question": ..., "expected_source_contains": [...]}`) through vector-only, FTS-only, and hybrid RRF search against the same indexed corpus, and reports Recall@K and MRR per strategy.

```bash
python evaluation_scripts/eval_retrieval_relevance.py --dataset evaluation_scripts/eval_dataset_supervised_learning.json
python evaluation_scripts/eval_retrieval_relevance.py --dataset evaluation_scripts/eval_dataset_exact_terms.json --out-csv evaluation_scripts/results.csv
```

Findings from the staging corpus (29 docs / 771 chunks) are summarized in the README's "Retrieval evaluation" section: hybrid ties dense-only on plain-English questions (both hit a 100% Recall@4 ceiling — no room for a second signal to help) and beats it on exact-term/parameter-name questions (+4.8% Recall@4, +10.3% MRR, N=22). Build a bigger or differently-scoped question set the same way (`expected_source_contains` matches on a substring of `source_file`, e.g. a URL slug like `tree.html`) before trusting a number for anything beyond a smoke test.

### Retrieval latency (p95)

`evaluation_scripts/benchmark_retrieval_latency.py` times `storage.retriever.hybrid_search()` directly — query embedding plus the RRF SQL transaction — not the full `/api/v1/query` endpoint, since the LLM generation call there (1–3s) would swamp the effect of the HNSW/GIN indexes, connection pooling, and pre-cached model weights the number is meant to isolate.

```bash
docker exec -it staging-rag-backend python evaluation_scripts/benchmark_retrieval_latency.py --iterations 100 --warmup 10
```

Run it more than once before trusting the result — a cold container (embedding-model lazy-load, connection-pool ramp-up, Docker Desktop contention right after `up`) can produce an outlier several times higher than steady state. Three runs against staging landed p95 between 150ms and 180ms; a fourth immediately after container start read 443ms and did not repeat.

---

## 8) Tests

Local (with env that can import `core.config`—`DB_PASSWORD` must be set even if tests mock the DB):

```bash
pip install -r requirements-backend.txt pytest pytest-asyncio httpx
pytest -q
```

CI (`.github/workflows/ci.yml`): on push/PR to `main` (and push to `feature/cycle3-enterprise-platform`), Ubuntu, Python 3.11, pip cache on `requirements-backend.txt`, service `pgvector/pgvector:pg16`, `pytest -v`.

---

## 9) Production (Terraform + Cloud Run)

Images expected by `infra/main.tf` (tag `v4.1` as of this write-up):

- `${region}-docker.pkg.dev/${project_id}/enterprise-rag-repo/api-service:<tag>`
- `${region}-docker.pkg.dev/${project_id}/enterprise-rag-repo/frontend-ui:<tag>`

Backend: **4 GiB / 4 vCPU**, max instances **3**, Direct VPC egress `PRIVATE_RANGES_ONLY` to Cloud SQL.  
Frontend: **1 GiB / 1 vCPU**, max instances **2**, ingress **internal load balancer**, `BACKEND_API_URL` = API Cloud Run URI.

Cloud SQL: `POSTGRES_15`, `db-f1-micro`, **10 GB** HDD, **no public IPv4**, private VPC peering. Align this with cost/capacity before a real production load.

### Step 1 — Bootstrap Artifact Registry

```bash
cd infra
terraform apply -target=google_artifact_registry_repository.rag_repository -var-file="terraform.tfvars"
```

### Step 2 — Build and push

Build `Dockerfile.backend` and `Dockerfile.frontend`, tag to the paths above, push to Artifact Registry. Update the image tag in Terraform if you do not use `v4.1`.

### Step 3 — Full apply

```bash
cd infra
terraform apply -var-file="terraform.tfvars"
```

After the API is up, run `db-init` once against Cloud SQL (from a network that can reach the private IP—typically a jump/bastion, Cloud Run job, or authorized VPC path). Schema is not created by Terraform.

Set `terraform.tfvars` for project, region, DB user/name/password, API keys, IAP OAuth client, and IAP accessor identity. Do not commit `terraform.tfvars` if it contains secrets.

---

## 10) Security posture (as configured)

**In place**

- `X-API-Key` on `/api/v1/*`
- Secret Manager for DB password, OpenAI key, API key; Cloud Run SA with `secretAccessor`
- Cloud SQL private IP only
- IAP on the HTTPS load balancer backend; accessor IAM is a named user in `infra/main.tf`
- Frontend Cloud Run ingress limited to the load balancer

**Known exposure**

Both Cloud Run services grant `roles/run.invoker` to **`allUsers`**. That lets the LB and the UI call the API without Cloud Run-level private invokers. **Do not treat this as a locked-down private mesh.** Tighten invokers and/or put the API behind IAP or identity tokens before handling sensitive corpora.

**Ingest process model**

API ingest is an in-process background task. Cloud Run can recycle the instance and **interrupt long crawls**. For durable jobs, move ETL to Cloud Run jobs, Cloud Tasks, or a worker—not documented as implemented today.

---

## 11) Guardrails operators will hit

| Guardrail | Behavior |
|---|---|
| File / download > **10 MB** | Dropped |
| `.zip`, `.exe`, images, media, etc. | Dropped (path and/or MIME) |
| Duplicate SHA-256 | Skipped (JSON ledger under `RAW_DATA_DIR`) |
| Same `source_file` already in DB | Skipped (no re-embed) |
| Web links outside `scikit-learn.org` or without `/stable/` | Not queued |
| Embedding dim ≠ **1536** | Provider raises |

If ingest “does nothing,” check path existence, extension list, domain lock, and whether files were already indexed (`python cli.py status`).

---

## 12) Troubleshooting

| Symptom | What to check |
|---|---|
| **401** on `/api/v1/*` | `X-API-Key` vs `API_KEY` in the **backend** process. Streamlit must have the same `API_KEY`. |
| UI: cannot reach backend | `BACKEND_API_URL`, Uvicorn up, `/health` within 2s |
| DB connection errors | `DB_HOST`/`DB_PORT` for this env (local **5433**, Compose internal **5432** / host **5434**). Run `cli.py db-init`. Password special characters should be encoded automatically. |
| `DB_PASSWORD` validation error | Variable missing in env file / shell |
| LLM “credentials missing” | Set `OPENAI_API_KEY` or `GITHUB_TOKEN` |
| “Live LLM Orchestration Error” | Token, quota, or network to OpenAI / GitHub Models; see backend logs |
| Empty or weak answers | Corpus empty? Hybrid search needs indexed rows. Re-ingest. Citations expander in the UI lists `source_file`. |
| Ingest 202 but no rows | Background task crashed (container logs); guardrails; domain lock; instance killed mid-job |
| Slow first query | Embedding model lazy-load; first encode after process start |
| Import / CI config tests | Tests mutate `os.environ`; `DB_PASSWORD` must exist for `get_settings()` in some cases |
| Cloud SQL from laptop | Private IP is not reachable without VPC access—do not expect `127.0.0.1` against production SQL |

---

## 13) Useful log markers

Backend / CLI print prefixes such as `[EMBEDDER]`, `[GUARDRAIL BLOCK]`, `[DEDUPLICATION SKIP]`, `[RETRIEVAL]`, `[DATABASE POOL]`, `[Audit Ledger Logged]`. Pipeline outcomes are also in `GET /api/v1/logs` and the Streamlit ledger table.
