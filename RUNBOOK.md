# 📘 Enterprise Hybrid RAG Platform - Operational Runbook

**Version:** 3.0.0  
**Architecture:** Serverless FastAPI + Streamlit UI + GCP Cloud SQL (pgvector) + Cloud Run  
**Core Embedding:** `Orange/orange-nomic-v1.5-1536` (Pre-cached)  
**LLM Inference:** GitHub Models (GPT-4o-mini)

---

## 🏗️ 1. Architecture & Environment Contract

This project enforces a strict **"Single Source of Truth" environment contract** to prevent configuration drift between Development, Staging, and Production.

### Environment Contract

| Configuration | Value |
|---|---|
| **Canonical Database Name** | `enterprise_rag_db` |
| **Canonical Database Port** | `5432` (Internal) |

### Configuration Files

- `.env.template` — Baseline environment schema. **Always commit this file.**
- `.env.development` — Used for local Python/Uvicorn development. **Git ignored.**
- `.env.staging` — Used by Docker Compose for the staging environment. **Git ignored.**
- `.env.production` — Used **only locally** to run migrations through the Cloud SQL Proxy. **Git ignored.**
- `infra/terraform.tfvars` — Used to inject variables and secrets into GCP. **Git ignored.**

---

## 💻 2. Local Development Setup

To test code changes without impacting cloud environments, run the database locally using Docker.

The local Docker database is mapped to port `5433` to avoid conflicts with native PostgreSQL installations.

### Step 1: Spin Up the Local Database

```bash
docker run \
  --name local-rag-db \
  -e POSTGRES_PASSWORD=your_secure_password \
  -e POSTGRES_DB=enterprise_rag_db \
  -p 5433:5432 \
  -d pgvector/pgvector:pg16
```

### Step 2: Configure Environment

Ensure `.env.development` contains:

```env
APP_ENV=DEVELOPMENT
DB_HOST=127.0.0.1
DB_PORT=5433
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_NAME=enterprise_rag_db
API_KEY=dev-local-secret-key-123
```

### Step 3: Initialize & Run

#### Initialize the Database

Create the required tables and indexes:

```bash
python cli.py db-init
```

#### Start the Backend API

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 3. Staging Deployment (Integration Testing)

Staging uses **Docker Compose** to test the interaction between the UI, API, and database in an isolated container network.

### Step 1: Spin Up the Stack

Explicitly pass `--env-file` so Docker Compose can correctly interpolate environment variables.

```bash
docker-compose \
  --env-file .env.staging \
  -f docker-compose.staging.yml \
  up -d --build
```

> **Note:** The staging database is mapped to host port `5434` for external inspection.

### Step 2: Initialize the Staging Schema

Run the initialization script inside the running backend container:

```bash
docker exec -it staging-rag-backend python cli.py db-init
```

---

## 🚀 4. Production Deployment (GCP Serverless)

Production relies entirely on **Terraform** for infrastructure provisioning and **Google Secret Manager** for runtime variable injection.

Because Cloud Run requires a valid container image during initialization, deployments must strictly follow this **3-step sequence**.

### Step 1: Provision Artifact Registry

First, provision only the container registry to break the Infrastructure-as-Code dependency between the registry and Cloud Run.

```bash
cd infra

terraform apply \
  -target=google_artifact_registry_repository.rag_repository \
  -var-file="terraform.tfvars"
```

### Step 2: Build & Push the "PyTorch Diet" Image

The backend image pre-caches the approximately 500 MB embedding model.

The image build and push may take several minutes.

#### Configure Docker Authentication

```bash
cd ..

gcloud auth configure-docker us-central1-docker.pkg.dev
```

#### Build the Backend Image

```bash
docker build \
  -f Dockerfile.backend \
  -t us-central1-docker.pkg.dev/<GCP_PROJECT_ID>/enterprise-rag-repo/api-service:v1.0 \
  .
```

#### Push the Image

```bash
docker push \
  us-central1-docker.pkg.dev/<GCP_PROJECT_ID>/enterprise-rag-repo/api-service:v1.0
```

### Step 3: Full Infrastructure Apply

Deploy the complete production infrastructure, including:

- Cloud SQL
- Google Secret Manager
- VPC networking
- Cloud Run
- Supporting infrastructure

Run:

```bash
cd infra

terraform apply -var-file="terraform.tfvars"
```

---

## 🔐 5. Production Database Management

Production databases run on **private VPC IP addresses (`10.x.x.x`)**.

You **cannot connect to the production database directly over the public internet**.

### Running Migrations or Seeding Production Data

Follow these steps when database migrations or seed operations are required.

### Step 1: Temporarily Enable Public Proxy Access

In `infra/main.tf`, temporarily change:

```terraform
ipv4_enabled = true
```

in the Cloud SQL database configuration.

Then apply the Terraform configuration:

```bash
terraform apply -var-file="terraform.tfvars"
```

### Step 2: Open the Secure Cloud SQL Tunnel

Start the Cloud SQL Auth Proxy on port `5435` to avoid local port conflicts:

```bash
cloud-sql-proxy \
  <GCP_PROJECT_ID>:<REGION>:<INSTANCE_NAME> \
  --port 5435
```

### Step 3: Run the CLI Tool

Ensure `.env.production` is configured with:

```env
DB_PORT=5435
```

Then execute the database initialization or migration command:

```powershell
$env:APP_ENV="PRODUCTION"; python cli.py db-init
```

### Step 4: Lock Down the Database

After completing the migration or seed operation:

1. Revert:

```terraform
ipv4_enabled = false
```

2. Apply Terraform again:

```bash
terraform apply -var-file="terraform.tfvars"
```

This returns the database to a **private VPC-only configuration**.

---

## 🛡️ 6. Security & Ingestion Guardrails

### API Security

All `/api/v1/*` routes are protected by an `X-API-Key` middleware.

The API key is securely injected into the Cloud Run container using **Google Secret Manager**.

Requests without a valid API key are rejected with:

```text
401 Unauthorized
```

### Cloud Run Edge Invocation

Cloud Run IAM is configured as **private**.

Direct access to the Cloud Run service requires a valid Google Cloud Identity Bearer Token.

Requests without a valid identity token are rejected at the Cloud Run edge with:

```text
403 Forbidden
```

### Ingestion Limits

The `DynamicWebCrawlerConnector` implements multiple safeguards to prevent excessive resource consumption:

- Uses **HTTP streaming** instead of loading entire responses into memory.
- Enforces a strict **10 MB payload size limit**.
- Validates the `Content-Type` / MIME type before parsing.
- Prevents oversized or unsupported payloads from reaching the processing pipeline.
- Reduces the risk of **Cloud Run Out-of-Memory (OOM)** kills.

---

## 🔒 Security Model Summary

The production environment follows a defense-in-depth architecture:

```text
                    Internet
                       │
                       ▼
             ┌───────────────────┐
             │   Cloud Run IAM   │
             │ Google Identity   │
             │      Token        │
             └─────────┬─────────┘
                       │
                 403 if invalid
                       │
                       ▼
             ┌───────────────────┐
             │   FastAPI API     │
             │   X-API-Key       │
             │    Middleware     │
             └─────────┬─────────┘
                       │
                 401 if invalid
                       │
                       ▼
             ┌───────────────────┐
             │ Protected API     │
             │     Routes        │
             └─────────┬─────────┘
                       │
                       ▼
             ┌───────────────────┐
             │   RAG Pipeline    │
             │                   │
             │ Ingestion / Query │
             └───────────────────┘
```

### Authentication Layers

| Layer | Security Control | Failure Response |
|---|---|---|
| **Edge** | Cloud Run IAM / Google Identity Token | `403 Forbidden` |
| **Application** | FastAPI `X-API-Key` Middleware | `401 Unauthorized` |
| **Secrets** | Google Secret Manager | Runtime secret injection |
| **Database** | Private VPC / Cloud SQL | No direct public access |
| **Ingestion** | 10 MB limit + MIME validation | Payload rejected |

---

## 📋 Environment Port Reference

| Environment | Database Host | Database Port | Purpose |
|---|---|---:|---|
| **Development** | `127.0.0.1` | `5433` | Local Docker PostgreSQL |
| **Staging** | Docker network | `5432` | Container-to-container communication |
| **Staging (Host)** | `127.0.0.1` | `5434` | External database inspection |
| **Production** | Private VPC IP | `5432` | Cloud SQL internal access |
| **Production Migration** | Cloud SQL Proxy | `5435` | Temporary secure migration access |

---

## ✅ Operational Checklist

### Local Development

- [ ] Start the local pgvector database.
- [ ] Configure `.env.development`.
- [ ] Run `python cli.py db-init`.
- [ ] Start the FastAPI application.
- [ ] Verify API functionality.

### Staging

- [ ] Configure `.env.staging`.
- [ ] Start Docker Compose.
- [ ] Verify UI/API/database connectivity.
- [ ] Run the staging database initialization.
- [ ] Execute integration tests.

### Production

- [ ] Provision Artifact Registry.
- [ ] Build the backend container image.
- [ ] Push the image to Artifact Registry.
- [ ] Run the full Terraform deployment.
- [ ] Verify Cloud Run IAM configuration.
- [ ] Verify Secret Manager injection.
- [ ] Verify Cloud SQL private networking.
- [ ] Run production smoke tests.

### Production Database Operations

- [ ] Temporarily enable Cloud SQL public proxy access.
- [ ] Apply Terraform.
- [ ] Start Cloud SQL Auth Proxy.
- [ ] Configure `.env.production` with `DB_PORT=5435`.
- [ ] Run the required CLI migration/seed command.
- [ ] Disable public IP access.
- [ ] Re-apply Terraform.
- [ ] Verify the database is private again.