---
name: run-tests
description: Run the correct test suite for this project. Knows the Docker exec
  pattern, pytest marker system, and frontend vs backend separation.
disable-model-invocation: true
---

# Run Tests

## Backend tests (via docker exec)

All backend tests run inside the `mt-backend` container. The container must be running (`docker compose -f docker-compose.dev.yml up`).

### Unit tests only (fast, no IO)
```bash
docker exec mt-backend pytest -m unit -v
```

### Integration tests (requires testcontainers — Postgres + Redis)
```bash
docker exec mt-backend pytest -m integration -v
```

### E2E tests (full ASGI client, real DB schema)
```bash
docker exec mt-backend pytest -m e2e -v
```

### All backend tests with coverage report
```bash
docker exec mt-backend pytest --cov=app --cov-report=term-missing
```

### Skip Neo4j tests (default — no local Neo4j required)
```bash
docker exec mt-backend pytest -m "not neo4j_real"
```

### Run a specific file or test
```bash
docker exec mt-backend pytest tests/unit/services/matching/test_adapter_registry.py -v
docker exec mt-backend pytest tests/unit/services/matching/test_adapter_registry.py::TestAdapterRegistry::test_get_fetcher -v
```

## Frontend tests

```bash
pnpm --filter mt-pricing-frontend test
```

Or from the frontend directory:
```bash
cd mt-catalogo && pnpm test
```

## All tests (monorepo — backend + frontend)
```bash
pnpm test
```

## Marker reference

| Marker | Meaning | Runs IO? |
|--------|---------|----------|
| `unit` | Pure unit tests, mocked dependencies | No |
| `integration` | Requires real Postgres + Redis via testcontainers | Yes |
| `e2e` | Full ASGI client with real DB schema | Yes |
| `neo4j_real` | Requires a running local Neo4j instance | Yes |

**Default run** (`pytest` with no marker filter) runs ALL tests including integration and e2e — this is slow. Use `-m unit` during active development.

## Common issues

**Container not running:** `docker compose -f docker-compose.dev.yml up -d` then retry.

**Test DB not migrated:** Integration/e2e tests use testcontainers that auto-migrate on start. If they fail with schema errors, check that `alembic/versions/` is mounted (it is, via bind mount in docker-compose.dev.yml).

**Coverage report missing a module:** Add it to `[tool.coverage.run] source` in `pyproject.toml`.
