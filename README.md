# Enterprise RAG System

A production-shaped **Retrieval-Augmented Generation** platform: ingest mixed-format documentation, index it in PostgreSQL with pgvector, and answer questions with **hybrid search** and **source citations**—not an unconstrained chatbot.

The current corpus and system prompt are specialized for **scikit-learn** technical documentation (local files or a domain-locked crawl of `scikit-learn.org/stable/`). The same pipeline is format-pluggable for other internal knowledge bases.

**How to run, deploy, and operate this repo:** see [RUNBOOK.md](RUNBOOK.md).

---

## Why it exists

Support and engineering teams cannot reliably query large, mixed-format docs. Generic LLMs invent APIs and hyperparameters. This system:

1. **Extracts** text from local directories or a scoped web crawl.
2. **Chunks, embeds, and indexes** content with lineage (`source_file`, `chunk_index`, format).
3. **Retrieves** with dense vectors *and* full-text search, fused by Reciprocal Rank Fusion (RRF) in SQL.
4. **Generates** answers grounded in retrieved blocks, with citations and an explicit refusal when context is missing.

Operators use a Streamlit console, a FastAPI service, or a CLI—the same engine behind all three.

---

## Recruiter snapshot

Built as a **data / AI / platform** project spanning ETL, vector retrieval, LLM orchestration, and GCP infrastructure as code.

| Theme | What shipped |
|---|---|
| **Data ingestion reliability** | Streaming connectors, 12+ parsers, SHA-256 + `source_file` dedup, 10 MB payload/MIME guardrails, crawl domain/path lock, pipeline SUCCESS/FAILED audit |
| **AI retrieval accuracy** | Hybrid pgvector + English FTS, RRF in Postgres, top-4 cited chunks, temperature-0 grounded `gpt-4o-mini`, Nomic 1536-d embeddings with a dimension guard; validated with a Recall@K/MRR eval harness (+7.9% MRR over vector-only on exact-term queries, confirmed across two corpus sizes) |
| **Backend performance** | Batched embeds (32) and DB writes (250), HNSW + GIN indexes, threaded connection pool on the query path, lazy + Docker-pre-cached SentenceTransformer, CPU-only PyTorch |
| **Data platform** | Env-profiled config, Docker Compose staging, Terraform (Cloud Run, private Cloud SQL, Secret Manager, IAP, Artifact Registry), GitHub Actions + live pgvector CI |

---

## Architecture

```
Streamlit console ─┐
CLI (db-init /     ├─► FastAPI (X-API-Key on /api/v1/*)
  ingest / query) ─┘         │
                             ├─ POST /ingest (202) ──► background ETL
                             │     connectors → parse/chunk → embed → Postgres
                             └─ POST /query
                                   embed question → hybrid RRF SQL → LLM → {answer, citations}
```

| Layer | Implementation |
|---|---|
| API | FastAPI `app.py` — health, status, logs, query, async ingest |
| UI | Streamlit `app_ui.py` — grounded chat + ingestion command center |
| Ops CLI | `cli.py` — schema init, ingest, query, corpus metrics |
| Config | `core/config.py` — pydantic-settings; `APP_ENV` → DEVELOPMENT / STAGING / PRODUCTION |
| Ingestion | `ingestion/` + `components/embedder.py` |
| Retrieval + LLM | `storage/retriever.py` + `components/orchestrator.py` |
| Store | PostgreSQL + pgvector (`enterprise_documents`, `pipeline_runs`) |
| Infra | `infra/` Terraform on GCP |

There is **no separate object store or job queue**. Persistence is Postgres. Ingest from the API runs in **FastAPI `BackgroundTasks`** (in-process), not a durable worker.

---

## Data ingestion (reliability)

**Connectors**

- **Local:** recursive walk of allowed extensions (txt, md, html, pdf, docx, xlsx, pptx, xml, py, json, ini, yaml/yml), yielded as a generator so files are not all loaded at once.
- **Web:** BFS crawler with `User-Agent: EnterpriseRAGBot/3.0`, **domain lock** (`scikit-learn.org`), **path filter** (`/stable/`), default **50-page** cap, **0.5s** delay, streaming HTTP with **10 MB** `Content-Length` / streamed-size abort and MIME blocking (video/audio/image/zip/executables).

**Pipeline (`IngestionPipeline`)**

- **10 MB** in-memory payload cap (Cloud Run OOM protection).
- Forbidden binaries/archives/images dropped before parse.
- **SHA-256** content ledger (JSON under `RAW_DATA_DIR`) plus a **DB skip** if `source_file` is already indexed (avoids re-embed).
- Extension-routed parsers (BeautifulSoup/lxml, pypdf, python-docx, openpyxl, python-pptx; code/config via a shared XML/code parser).
- NUL-byte sanitization so Postgres text columns stay valid.
- LangChain `RecursiveCharacterTextSplitter` — **1000** characters, **150** overlap, with `chunk_index` lineage.
- Per-file parser/transform failures return empty chunks instead of aborting the whole run.

**Load**

- Configurable embedding buffer (API default **50**; CLI `--batch-size`).
- SentenceTransformer `embed_batch` with **batch_size=32**.
- `psycopg2.extras.execute_values` in **250-row** sub-batches.
- `PipelineLogger` writes RUNNING → SUCCESS/FAILED with extracted / transformed / indexed counts.

---

## Retrieval and generation (accuracy)

**Embeddings:** `Orange/orange-nomic-v1.5-1536` via `sentence-transformers`. Model is **lazy-loaded** on first request and **pre-downloaded in the backend Docker image** to avoid Cloud Run cold-start timeouts. A startup encode **must** return **1536** dimensions or ingest/query fails closed.

**Hybrid search (single SQL transaction):**

1. Query embedding (cosine distance on `vector`).
2. English `tsvector` / `plainto_tsquery` full-text search (`ts_rank_cd`).
3. Candidate window = `top_k × 5` (default top_k **4** → **20** per strategy).
4. **RRF** in SQL: `1/(60 + rank)` from each list, summed, ordered, limited to **4** chunks.

Indexes: **HNSW** (`vector_cosine_ops`) and **GIN** on a generated `tsvector` column.

**Orchestration:** retrieved blocks are formatted with format, RRF score, source, and chunk offset. The system prompt is a technical-support persona that must use provided context (and refuse if it cannot). Generation uses **gpt-4o-mini**, **temperature 0.0**. Credentials: `OPENAI_API_KEY` first, else `GITHUB_TOKEN` against GitHub Models (`https://models.github.ai/inference`). Response payload: answer + sorted unique source citations.

`EMBEDDING_MODE` is `LOCAL` vs `CLOUD` by environment in config; the provider currently **always** runs the local Nomic model (staging/prod still size Cloud Run for PyTorch).

---

## Retrieval evaluation

Hybrid search's benefit is measured, not assumed. `evaluation_scripts/` holds a harness (`eval_retrieval_relevance.py`, `benchmark_retrieval_latency.py`, `trace_hybrid_search.py`) that compares vector-only, FTS-only, and hybrid RRF search on the same corpus using Recall@4 and MRR — see [RUNBOOK.md](RUNBOOK.md) for how to run it. Both question sets were re-run unchanged against a corpus 3× the size of the original to check the findings weren't an artifact of a small, curated test set.

| Question set (N) | Corpus | Vector-only | FTS-only | Hybrid RRF |
|---|---|---|---|---|
| Conceptual, plain-English (36) | 29 docs / 771 chunks | Recall 100% / MRR 0.880 | Recall 30.6% / MRR 0.257 | Recall 100% / MRR 0.863 |
| Conceptual, plain-English (36) | 101 docs / 1,982 chunks | Recall 100% / MRR 0.870 | Recall 30.6% / MRR 0.252 | Recall 94.4% / MRR 0.831 |
| Exact-term: parameter/class names (22) | 29 docs / 771 chunks | Recall 95.5% / MRR 0.886 | Recall 54.6% / MRR 0.545 | Recall 100% / MRR 0.977 |
| Exact-term: parameter/class names (22) | 101 docs / 1,982 chunks | Recall 90.9% / MRR 0.864 | Recall 54.6% / MRR 0.545 | **Recall 95.5% / MRR 0.932** |

Dense-only retrieval is already at a recall ceiling on conceptual questions, so hybrid can only tie there — and slightly loses on MRR by blending in a weaker FTS signal; the effect held (and got slightly more pronounced, not less) at the larger corpus. On exact-term questions dense-only is not saturated, and hybrid RRF measurably wins at both scales — **+5.0% Recall@4, +7.9% MRR** at the larger, more credible corpus (vector-only's own edge also shrinks as more distractor pages enter the corpus). Traced mechanism: a question about `SelectKBest` returned nothing relevant from vector search alone; full-text search matched the exact token at rank 1, and RRF fusion pulled it into hybrid's result. Full per-question output is in `evaluation_scripts/results_*.csv`.

**Retrieval latency:** `hybrid_search()` (query embed + the RRF SQL transaction, no LLM call) measured at **p95 ≈ 150–180ms** across three independent runs of 100 calls each (staging; HNSW + GIN indexes, pooled connections, pre-cached embedding model). A cold-container run read 443ms and did not repeat. `trace_hybrid_search.py --explain` later found the query forcing a full-table `Seq Scan`; unioning the two search CTEs' candidate ids before the final join fixed it (`Index Scan using enterprise_documents_pkey`) and roughly halved raw SQL execution time (4.83ms → 2.44ms, matched conditions) — but didn't move end-to-end p95, since the CPU embedding call dominates total latency at this corpus size, not the SQL. See `evaluation_scripts/results_latency.csv` and `latency_before_fix.csv` / `latency_after_fix.csv`.

---

## Data model

**`enterprise_documents`**

- `text_content`, `source_file`, `doc_format`, `chunk_index`
- `embedding vector(1536)`
- `text_vector tsvector` generated from `text_content` (`english`)

**`pipeline_runs`**

- UUID `run_id`, pipeline name, environment, enum status (`RUNNING` / `SUCCESS` / `FAILED`)
- record counts, timestamps, `error_message`

Schema is idempotent via `python cli.py db-init` (`storage/db_seeder.py`).

---

## Backend performance and serving

- Query/status/logs use a **threaded connection pool** (min **1**, max **20**). Ingest/audit still open short-lived connections.
- CPU-only PyTorch wheels in `Dockerfile.backend`; backend Cloud Run **4 GiB / 4 vCPU** (embeddings in process); frontend **1 GiB / 1 vCPU**.
- API ingest returns **202 Accepted** so the HTTP request is not tied to full ETL duration (instance recycle can still interrupt in-process tasks).
- Streamlit timeouts: health **2s**, status/logs **3s**, ingest trigger **5s**, query **30s**.
- Uvicorn on `${PORT:-8000}` for Cloud Run; Streamlit on `${PORT:-8501}`.

---

## Platform, security, and CI

**Environments:** `APP_ENV` loads `.env.development` / `.env.staging` / `.env.production`. `DB_PASSWORD` is required; `SQLALCHEMY_DATABASE_URI` is assembled with URL-encoded passwords (or taken from the environment).

**Auth:** `X-API-Key` on all `/api/v1/*` (401 on mismatch). `/health` is public. Secrets stay in env / Secret Manager—not in source.

**GCP (Terraform `infra/`):** dedicated Cloud Run service account; Secret Manager for DB password, OpenAI key, API key; VPC + private Cloud SQL (`ipv4_enabled = false`); Artifact Registry; HTTPS load balancer + **IAP** on the frontend backend service.

**Current IAM note:** Cloud Run invoker is bound to `allUsers` so the load balancer and UI can reach services. That is **not** private-invoker isolation; application auth is the API key. Details in the runbook.

**CI:** GitHub Actions on `main` (and the platform feature branch) — Python 3.11, pip cache, `pgvector/pgvector:pg16` service, pytest (API auth, ingestion guardrails, config validation).

**Tests of record:** oversized payload drop, forbidden extensions, hash-ledger skip, parser registry routing, API 200/202 with mocked RAG/ingest, fail-fast missing `DB_PASSWORD`.

---

## Stack

| Area | Libraries / services |
|---|---|
| API | FastAPI, Uvicorn, Pydantic v2 |
| UI | Streamlit, pandas, requests |
| DB | PostgreSQL 16 locally / Compose; Cloud SQL POSTGRES_15 in Terraform; pgvector; psycopg2 |
| NLP / LLM | sentence-transformers, transformers, OpenAI SDK |
| ETL | BeautifulSoup, lxml, pypdf, python-docx, openpyxl, python-pptx, langchain_text_splitters |
| Deploy | Docker (backend/frontend), Compose staging, Terraform (Cloud Run, SQL, Secret Manager, IAP) |

Python **3.11+**.

---

## Repository map

```
app.py                 FastAPI service
app_ui.py              Streamlit operator console
cli.py                 db-init / ingest / query / status
core/config.py         Environment-aware settings
components/            Embedder ETL, embedding provider, RAG orchestrator
ingestion/             Connectors, parsers, dedup, chunk transformer
storage/               Pool, seeder, hybrid retriever, analytics, pipeline logger
evaluation_scripts/    Retrieval eval (Recall@K/MRR), latency benchmark, topic-scoped ingestion
infra/                 Terraform (GCP)
tests/                 Pytest (API, security, ingestion, config)
Dockerfile.backend / Dockerfile.frontend
docker-compose.staging.yml
RUNBOOK.md             Local, staging, production, CLI, troubleshooting
```

---

## Surfaces (reference)

Protected routes expect `X-API-Key`. Full commands and env vars live in [RUNBOOK.md](RUNBOOK.md).

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Liveness + `APP_ENV` (no key) |
| `GET` | `/api/v1/status` | Chunk counts by format |
| `GET` | `/api/v1/logs` | Recent `pipeline_runs` |
| `POST` | `/api/v1/query` | `{ question }` → `{ answer, citations }` |
| `POST` | `/api/v1/ingest` | `{ source_type, target_path, limit, batch_size }` → 202 background ETL |
