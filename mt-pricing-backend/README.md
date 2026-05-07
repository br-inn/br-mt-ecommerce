# mt-pricing-backend

Backend FastAPI + Celery para el sistema **MT Middle East — MDM + Pricing**.

- **Runtime**: Python 3.11, FastAPI 0.110+, SQLAlchemy 2.0 async, asyncpg, Celery 5.3.
- **Persistencia**: Supabase Postgres (rol `mt_app`) + Redis (broker/result).
- **Auth**: Supabase Auth (JWT) verificado por backend (ADR-031).
- **Migraciones**: Alembic (`public.*`) + Supabase migrations (`auth/storage/RLS`).
- **Workers**: 6 colas — `imports`, `pricing`, `images`, `comparator`, `notifications`, `audit`.
- **Scheduler**: `DatabaseScheduler` custom sobre `public.job_definitions` (ADR-046).

> Esta es la **estructura skeleton** (Sprint 0, Agente B). Modelos, repos, endpoints
> y migraciones reales los completan los Agentes C/F/G en sprints posteriores.

---

## Quickstart local

### Requisitos

- Python 3.11
- [uv](https://docs.astral.sh/uv/) (gestor de deps + venv)
- Postgres 15+ (Supabase local CLI o instancia remota dev)
- Redis 7+

### Setup

```bash
# 1. Instalar deps en venv local (uv crea .venv automáticamente)
uv sync

# 2. Configurar entorno
cp .env.example .env
# editar .env con credenciales locales (SUPABASE_*, DATABASE_URL, REDIS_URL)

# 3. (Cuando Agente C entregue migrations) aplicar schema
uv run alembic upgrade head

# 4. Levantar API
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Levantar worker Celery (en otra terminal)
uv run celery -A app.workers.worker worker \
    -Q imports,pricing,images,comparator,notifications,audit \
    -l info

# 6. Levantar scheduler (Beat con DatabaseScheduler — ADR-046)
uv run celery -A app.workers.worker beat \
    --scheduler app.scheduler.database_scheduler:DatabaseScheduler \
    -l info
```

API disponible en `http://localhost:8000`. Docs OpenAPI en `/docs` (sólo si `ENABLE_DOCS=true`).

### Healthchecks (ADR-048)

| Endpoint | Auth | Comprueba |
|---|---|---|
| `GET /health/live` | público | event loop responde |
| `GET /health/ready` | basic-auth | DB pool + Redis ping |
| `GET /health/db` | basic-auth | query trivial Postgres + pool stats |
| `GET /health/redis` | basic-auth | PING |
| `GET /health/storage` | basic-auth | list 1 file en Supabase Storage |
| `GET /health/celery` | basic-auth | heartbeat workers (custom, no `celery.control.ping`) |

---

## Tests

```bash
# Tests unitarios + integración (testcontainers levanta Postgres+Redis)
uv run pytest

# Sólo unit
uv run pytest -m unit

# Con coverage HTML
uv run pytest --cov-report=html
```

---

## Calidad de código

```bash
uv run ruff check .              # lint
uv run ruff format .             # format
uv run mypy app                  # type check estricto
uv run pip-audit                 # vulnerabilidades
```

---

## Estructura

```
app/
├── main.py                  # FastAPI factory + lifespan
├── core/                    # config, logging, db, supabase, redis, sentry
├── api/                     # routers + deps
│   ├── deps.py              # auth, get_db_session, etc.
│   └── routes/              # endpoints (Agente F/G)
├── services/                # lógica de dominio
│   ├── pricing/  comparator/  imports/  kb/  users/  audit/
├── repositories/            # data access (Agente G)
├── schemas/                 # Pydantic request/response
├── workers/                 # Celery
│   ├── worker.py            # Celery app factory
│   └── tasks/               # tasks por queue
├── scheduler/               # DatabaseScheduler (ADR-046)
└── db/                      # engine + ORM models (Agente C)

alembic/                     # migrations Postgres (Agente C)
tests/
├── unit/  integration/
└── conftest.py              # fixtures async + testcontainers
```

---

## Referencias

- `_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md` v1.4 §22.1
- `_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml`
- `_bmad-output/planning-artifacts/mt-jobs-module-design.md`
- ADRs: 029 (FastAPI), 030 (Celery), 031 (Supabase), 045 (persistencia híbrida),
  046 (DatabaseScheduler), 047 (observability), 048 (healthchecks).
