# TenantCore

[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16.0+-336791.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.4+-DC382D.svg)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**TenantCore** is a production-grade multi-tenant SaaS backend engine built with FastAPI, PostgreSQL Row-Level Security (RLS), Redis, and Arq. It enforces tenant data isolation at the database engine layer, provides distributed rate limiting and idempotency controls, processes background webhooks asynchronously, and exports structured telemetry and Prometheus metrics.

---

## Architecture Overview

```
                          ┌───────────────────────────┐
                          │   Reverse Proxy / Client  │
                          └─────────────┬─────────────┘
                                        │ HTTP / JSON
                                        ▼
                   ┌────────────────────────────────────────┐
                   │        TenantCore API (FastAPI)        │
                   │  - X-Request-ID Middleware Trace       │
                   │  - API Key Authentication              │
                   │  - Redis Sliding-Window Rate Limiter   │
                   └───────┬────────────────────────┬───────┘
                           │                        │
       Async SQLAlchemy    │                        │ Enqueue Jobs
       & SET LOCAL RLS     │                        │ (HMAC-Signed)
                           ▼                        ▼
           ┌───────────────────────┐        ┌───────────────────────┐
           │     PostgreSQL 16     │        │        Redis 7        │
           │  (Row-Level Security) │        │ (arq, Cache, Limits)  │
           └───────────────────────┘        └───────────┬───────────┘
                                                        │
                                                        │ Dequeue Tasks
                                                        ▼
                                            ┌───────────────────────┐
                                            │      Arq Worker       │
                                            │  (Retries & Backoff)  │
                                            └───────────┬───────────┘
                                                        │
                                                        │ Webhook Dispatch
                                                        ▼
                                            ┌───────────────────────┐
                                            │ Third-Party Endpoints │
                                            └───────────────────────┘
```

### Key Architectural Tenets

1. **Kernel-Level Multi-Tenancy (PostgreSQL RLS):** Tenant isolation is not delegated to application-layer `WHERE tenant_id = ...` clauses. Every database transaction sets `SET LOCAL app.current_tenant = :tenant_id`, and PostgreSQL policies (`FORCE ROW LEVEL SECURITY`) ensure that unauthorized rows are physically inaccessible to the application role (`app_user`).
2. **Least-Privilege Database Access:** Database schema migrations run under an administrative role (`postgres`), while API runtime queries execute under an unprivileged `app_user` role restricted from bypassing RLS policies.
3. **Resilient Background Processing:** Webhook events and high-latency notifications are decoupled from the HTTP request cycle using `arq` over Redis, featuring HMAC-SHA256 signature verification and exponential backoff retry scheduling.
4. **End-to-End Observability:** Distributed request tracing (`X-Request-ID`) correlates incoming HTTP calls with database transactions, background task IDs, and structured JSON logs. Native metrics are exposed via Prometheus at `/metrics`.
5. **Container Hardening:** Built on multi-stage Docker builds using non-root execution (`appuser:10001`), read-only container best practices, and deterministic `entrypoint.sh` lifecycle orchestration.

---

## Tech Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **API Framework** | FastAPI | `^0.110.0` | Asynchronous ASGI Web Framework |
| **ASGI Server** | Uvicorn | `^0.28.0` | High-concurrency production server |
| **Database** | PostgreSQL | `16-alpine` | Relational storage with native RLS |
| **Driver & ORM** | SQLAlchemy + asyncpg | `^2.0.28` / `^0.29.0` | Async database engine with connection pooling |
| **Migrations** | Alembic | `^1.13.0` | Asynchronous database migrations |
| **In-Memory Store** | Redis | `7-alpine` | Rate limiting, idempotency locks, task queue |
| **Task Queue** | Arq | `^0.25.0` | Async job queue running over Redis |
| **Validation** | Pydantic v2 | `^2.6.0` | Schema validation and settings management |
| **Telemetry** | Prometheus Client | `^0.20.0` | Real-time process and HTTP telemetry |

---

## Repository Structure

```text
TenantCore/
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Local development dependencies (Postgres + Redis)
├── docker-compose.prod.yml       # Production multi-container topology
├── Dockerfile                    # Multi-stage production container build
├── requirements.txt              # Pinned application dependencies
├── scripts/
│   └── entrypoint.sh             # Role-based container entrypoint (web vs worker)
├── app/
│   ├── core/
│   │   ├── config.py             # Pydantic Settings & environment variables
│   │   ├── security.py           # API Key hashing & HMAC-SHA256 helpers
│   │   ├── rate_limiter.py       # Sliding-window atomic Redis rate limiter
│   │   └── arq.py                # Arq Redis connection pool setup
│   ├── db/
│   │   ├── session.py            # Async engine & tenant-scoped session factory
│   │   └── migrations/           # Alembic async environment & version files
│   ├── models/
│   │   ├── base.py               # Declarative Base
│   │   ├── tenant.py             # Tenant entity model
│   │   └── invoice.py            # Invoice entity model with RLS policies
│   ├── schemas/                  # Pydantic request and response schemas
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── tenants.py    # Tenant provisioning endpoints
│   │   │   │   ├── invoices.py   # Invoice CRUD under tenant isolation
│   │   │   │   └── webhooks.py   # Payment webhook ingestion
│   │   │   └── router.py         # Versioned API route aggregator
│   │   └── deps.py               # Auth and tenant dependency injection
│   ├── workers/
│   └── arq_worker.py             # Arq WorkerSettings and webhook task handlers
│   └── main.py                   # FastAPI app instance, lifespans, and middleware
└── tests/
    ├── test_auth_pipeline.py     # API key verification & tenant creation
    ├── test_invoices.py          # RLS cross-tenant isolation & state tests
    ├── test_webhooks.py          # HMAC verification & payment state machine
    ├── test_rate_limiter.py      # Concurrency & burst rate limit tests
    ├── test_async_tasks.py       # Arq job execution & retry backoff tests
    └── test_observability.py     # Request tracing & Prometheus endpoint tests
```

---

## Quickstart (Local Development)

### 1. Clone & Set Up Python Environment

```powershell
git clone [https://github.com/your-org/TenantCore.git](https://github.com/your-org/TenantCore.git)
cd TenantCore

python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Launch Local Backing Services

Start isolated PostgreSQL and Redis containers for local development:

```powershell
docker compose up -d
```

### 3. Run Database Migrations

Apply database schemas, roles, and RLS policies:

```powershell
alembic upgrade head
```

### 4. Start the Application & Background Worker

Start the API server in your primary terminal:

```powershell
uvicorn app.main:app --port 8000 --reload
```

In a second terminal, start the background worker:

```powershell
.venv\Scripts\Activate.ps1
arq app.workers.arq_worker.WorkerSettings
```

---

## Production Deployment (Docker Compose)

The production stack deploys four containerized services configured with health checks and inter-service dependencies.

```powershell
# Build and deploy the production stack in detached mode
docker compose -f docker-compose.prod.yml up -d --build
```

### Verify Service Status

```powershell
docker compose -f docker-compose.prod.yml ps
```

| Service | Container Name | Status | Ports |
| :--- | :--- | :--- | :--- |
| `postgres` | `saas_postgres_prod` | `Up (healthy)` | Internal 5432 |
| `redis` | `saas_redis_prod` | `Up (healthy)` | Internal 6379 |
| `api` | `saas_api_prod` | `Up` | `0.0.0.0:8000->8000` |
| `worker` | `saas_worker_prod` | `Up` | Internal |

---

## API Usage & Verification

### 1. Health & Telemetry

```bash
# Check service health and dependency connectivity
curl -i http://localhost:8000/health

# Scrape Prometheus metrics
curl http://localhost:8000/metrics
```

### 2. Tenant Provisioning

```powershell
$tenant = curl.exe -s -X POST http://localhost:8000/api/v1/tenants `
  -H "Content-Type: application/json" `
  -d '{\"name\": \"Acme Production Corp\"}' | ConvertFrom-Json

$apiKey =$tenant.api_key
$tenantId =$tenant.id
Write-Host "Tenant ID: $tenantId"
Write-Host "API Key: $apiKey"
```

### 3. Create an Invoice Under RLS Isolation

```powershell
$invoice = curl.exe -s -X POST http://localhost:8000/api/v1/invoices `
  -H "Content-Type: application/json" `
  -H "X-API-KEY: $apiKey" `
  -d '{\"customer_name\": \"Cyberdyne Systems\", \"amount\": 4500.00, \"currency\": \"USD\"}' | ConvertFrom-Json

$invoiceId =$invoice.id
Write-Host "Invoice Created: $invoiceId (Status: $($invoice.status))"
```

### 4. Ingest an Inbound Payment Webhook (HMAC-SHA256)

```python
import hashlib, hmac, json, httpx

payload = {
    "event_id": "evt_live_1001",
    "event_type": "payment.succeeded",
    "data": {
        "invoice_id": "<INVOICE_ID>",
        "tenant_id": "<TENANT_ID>",
        "callback_url": "[https://httpbin.org/post](https://httpbin.org/post)",
    },
}
raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
secret = "whsec_test_secret_key_998877"
signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

res = httpx.post(
    "http://localhost:8000/api/v1/webhooks/payments",
    content=raw_body,
    headers={"Content-Type": "application/json", "X-Signature": signature},
)
print(res.json())
```

---

## Row-Level Security Mechanics

PostgreSQL RLS ensures that queries automatically scope to the authenticated tenant:

```sql
-- 1. Enforce strict RLS on the table
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;

-- 2. Define the restrictive tenant isolation policy
CREATE POLICY tenant_isolation_policy ON invoices
    AS RESTRICTIVE
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
```

On every database checkout, the async session executes:

```python
await db.execute(
    text("SET LOCAL app.current_tenant = :tenant_id"), {"tenant_id": tenant_id}
)
```

If an attacker attempts to inject a query across tenant boundaries or read records belonging to another customer, the PostgreSQL query engine returns an empty result set or raises a policy violation error directly at the database layer.

---

## Test Suite Execution

Run the full automated test suite containing 14 unit and integration tests across data isolation, rate limiting, and task pipelines:

```powershell
python -m pytest -v
```

### Coverage Breakdown

- **`test_auth_pipeline.py`**: Validates 401/403 responses on invalid API keys and verifies secure key generation.
- **`test_invoices.py`**: Verifies strict RLS isolation, cross-tenant leak prevention, and state transitions.
- **`test_rate_limiter.py`**: Tests sliding-window request throttling and concurrency burst enforcement in Redis.
- **`test_webhooks.py`**: Verifies HMAC signature generation, validation, and idempotent webhook processing.
- **`test_async_tasks.py`**: Tests `arq` background dispatch, retry scheduling on 5xx errors, and exponential backoff.
- **`test_observability.py`**: Ensures `X-Request-ID` correlation persistence and verifies Prometheus metric exports.

---

## Environment Configuration

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Deployment environment (`development` / `production`) |
| `DEBUG` | `False` | Enables verbose debugging and traceback exposure |
| `POSTGRES_SERVER` | `localhost` | PostgreSQL host address |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `saas_db` | Primary database name |
| `POSTGRES_USER` | `postgres` | Superuser account used for DDL migrations |
| `POSTGRES_PASSWORD` | `postgres_secret` | Password for migration superuser |
| `APP_DB_USER` | `app_user` | Unprivileged application role subject to RLS |
| `APP_DB_PASSWORD` | `app_secret` | Password for application runtime role |
| `REDIS_HOST` | `localhost` | Redis host address |
| `REDIS_PORT` | `6379` | Redis port |
| `WEBHOOK_SECRET` | `whsec_...` | HMAC-SHA256 signing secret for webhooks |
| `WEB_CONCURRENCY` | `4` | Number of Uvicorn workers in production containers |