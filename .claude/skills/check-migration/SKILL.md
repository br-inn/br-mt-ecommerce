---
name: check-migration
description: Validate and apply Alembic migrations in mt-pricing-backend. Guides
  the full workflow — pre-apply checks, schema split order, enum pitfalls, and
  post-apply verification. Use before applying any new migration.
disable-model-invocation: true
---

# Check Migration

## Pre-apply checklist

Before running any migration, verify:

1. **Check current DB state vs codebase head**
   ```bash
   docker exec mt-backend alembic current       # what revision is in DB
   docker exec mt-backend alembic heads         # what the codebase expects
   docker exec mt-backend alembic check         # exits non-zero if DB != head
   ```

2. **Review the new migration file**
   - File must be in `mt-pricing-backend/alembic/versions/`
   - Naming: `YYYYMMDD_NNN_short_description.py` (e.g. `20260519_131_add_price_index.py`)
   - `down_revision` must point to the current head, not skip any revision
   - No hardcoded secrets or environment-specific values

3. **Enum columns — mandatory rule**
   Any migration that maps a Python `Enum` to an existing PostgreSQL enum type MUST use:
   ```python
   # CORRECT — references existing PG type, does NOT try to CREATE TYPE
   sa.Column("status", sa.Enum("active", "inactive", name="product_status", create_type=False))

   # WRONG — asyncpg DatatypeMismatch at runtime
   sa.Column("status", sa.String)
   sa.Column("status", sa.Enum("active", "inactive", name="product_status"))  # no create_type=False
   ```
   Exception: if your migration also contains `op.execute("CREATE TYPE ...")` for a brand-new type, `create_type=False` is not needed for that new type.

4. **Schema split — apply order**
   - `public.*` tables → Alembic only (`./infra/scripts/migrate.sh`)
   - `auth.*` tables → Supabase migrations only (never Alembic)
   - `storage.*` tables → Supabase migrations only (never Alembic)
   - RLS policies → Supabase migrations only

   **Order when both are needed:** Apply Supabase migrations first, then Alembic.

## Applying the migration

```bash
# Run Alembic upgrade directly inside the backend container
docker exec mt-backend alembic upgrade head

# After migration, restart backend + worker
docker restart mt-backend mt-worker mt-beat

# Verify health
curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live
```

> Note: `./infra/scripts/migrate.sh` exists but is currently a placeholder stub — use `docker exec mt-backend alembic upgrade head` directly.

## Dry-run (SQL preview)

Preview the SQL without executing:
```bash
docker exec mt-backend alembic upgrade head --sql
```

## Downgrade (rollback)

```bash
# Roll back one step
docker exec mt-backend alembic downgrade -1

# Roll back to a specific revision
docker exec mt-backend alembic downgrade 20260516_068

# After rollback, restart backend
docker restart mt-backend mt-worker mt-beat
```

## Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Missing `create_type=False` on Enum | `asyncpg.exceptions.DatatypeMismatchError` at startup | Add `create_type=False` to the Enum column definition |
| Wrong `down_revision` | `alembic.util.exc.CommandError: Multiple head revisions` | Fix `down_revision` to point to the single current head |
| Applying Alembic before Supabase | FK constraint failure on `auth.users` or storage tables | Apply Supabase migration first via Supabase CLI |
| Missing index on FK column | Slow joins / sequential scans on large tables | Add `op.create_index` for every FK column in the migration |
| Non-idempotent data migration | Migration fails on re-run | Add `WHERE` clause to `op.execute` data updates |

## Verification after apply

```bash
docker exec mt-backend alembic current        # should show new head
docker exec mt-backend alembic check          # should exit 0
curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live   # should return {"status":"ok"}
```

If the backend fails to start after migration, check:
```bash
docker logs mt-backend --tail=50
```
Look for `DatatypeMismatch`, `OperationalError`, or `ProgrammingError` which indicate migration issues.
