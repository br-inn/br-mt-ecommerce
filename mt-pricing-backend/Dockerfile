# syntax=docker/dockerfile:1.7
# =============================================================================
# MT Middle East — Backend (FastAPI + Celery)
# Multi-stage:
#   - builder: instala deps con uv (compartido por dev/runtime).
#   - dev:     python:3.11-slim con todo el toolchain — hot-reload, debugging.
#   - runtime: distroless non-root para staging/prod (deploy real).
# Refs: mt-cicd-pipeline.md, ADR-029 (FastAPI), ADR-030 (Celery), ADR-048 (health).
# =============================================================================

# --- Stage 1: builder --------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* README.md ./
RUN uv pip install --system --no-cache .

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# --- Stage 1b: dev-builder (builder + dev deps) ------------------------------
# Sólo se usa para la imagen dev — añade pytest + testcontainers + ruff/mypy
# encima del builder base. NO se incluye en runtime.
FROM builder AS dev-builder
RUN uv pip install --system --no-cache \
    pytest>=8 \
    pytest-asyncio>=0.23 \
    pytest-cov>=4 \
    "testcontainers[postgresql,redis,neo4j]>=4" \
    respx>=0.20 \
    ruff>=0.3 \
    mypy>=1.9 \
    types-PyYAML \
    schemathesis>=3.27 \
    pip-audit

# --- Stage 2: dev (slim Python, hot-reload friendly) -------------------------
# Para docker-compose.dev.yml. Mantiene shell + tools + libpython compartido.
FROM python:3.11-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

# Tools útiles en dev: curl para healthchecks/scripts, libpq para psycopg, ca-certs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=dev-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=dev-builder /usr/local/bin /usr/local/bin
COPY --from=dev-builder /build/app /app/app
COPY --from=dev-builder /build/alembic /app/alembic
COPY --from=dev-builder /build/alembic.ini /app/alembic.ini

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

# Default command — overridable desde docker-compose (uvicorn --reload, celery, etc.)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- Stage 3: runtime (distroless, non-root) — staging/prod ------------------
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder --chown=nonroot:nonroot /build/app /app/app
COPY --from=builder --chown=nonroot:nonroot /build/alembic /app/alembic
COPY --from=builder --chown=nonroot:nonroot /build/alembic.ini /app/alembic.ini

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0) if urllib.request.urlopen('http://localhost:8000/health/live', timeout=2).status == 200 else sys.exit(1)"]

ENTRYPOINT ["python", "-m", "gunicorn", "app.main:app", \
    "--bind", "0.0.0.0:8000", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--workers", "2", \
    "--timeout", "60", \
    "--graceful-timeout", "30", \
    "--access-logfile", "-", \
    "--error-logfile", "-"]
