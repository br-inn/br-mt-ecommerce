# `infra/scripts/`

Scripts operativos para arrancar, parar y operar el stack MT Pricing localmente
con Docker, y deploy a entornos remotos (placeholders Sprint 2+).

## Despliegue local con Docker (Caddy entry point único)

| Script | Propósito | Bash | PowerShell |
|--------|-----------|------|------------|
| `dev-up` | Arranca todo el stack | `./infra/scripts/dev-up.sh` | `.\infra\scripts\dev-up.ps1` |
| `dev-down` | Para el stack | `./infra/scripts/dev-down.sh` | `.\infra\scripts\dev-down.ps1` |
| `check-ports` | Verifica puertos disponibles + sugiere alternativas | `./infra/scripts/check-ports.sh` | `.\infra\scripts\check-ports.ps1` |

### Uso típico

```bash
# Primera vez (genera .env.deploy si falta + verifica puertos)
./infra/scripts/dev-up.sh

# Modo background con rebuild
./infra/scripts/dev-up.sh -d --build

# Logs de un servicio
docker compose -f docker-compose.dev.yml --env-file .env.deploy logs -f backend

# Parar (preserva datos)
./infra/scripts/dev-down.sh

# Parar + borrar datos Postgres/Redis
./infra/scripts/dev-down.sh -v
```

PowerShell:
```powershell
.\infra\scripts\dev-up.ps1
.\infra\scripts\dev-up.ps1 -Detach -Build
.\infra\scripts\dev-down.ps1
.\infra\scripts\dev-down.ps1 -Volumes
```

### Modelo de despliegue local

```
Host machine
    |
    +-- localhost:${CADDY_HTTP_PORT}     <-- unico entry point HTTP (Caddy)
    |       |
    |       +-- routea internamente:
    |               /api/*    -> backend (FastAPI)
    |               /health/* -> backend
    |               /docs     -> backend (OpenAPI)
    |               /_next/*  -> frontend (Next.js HMR)
    |               /         -> frontend (catch-all)
    |
    +-- localhost:${POSTGRES_HOST_PORT}  <-- Postgres (solo IDE: DBeaver/psql)
    +-- localhost:${REDIS_HOST_PORT}     <-- Redis (solo IDE: redis-cli/Insight)

Docker network mt-internal (NO expuesta al host):
    backend:8000 . frontend:3000 . worker . beat . postgres:5432 . redis:6379 . caddy:80
```

Backend y frontend NO se exponen al host directamente — solo accesibles vía
Caddy. Esto es intencional: simula el modelo de producción donde un único proxy
es la frontera con el internet (alineado con ADR-035).

### Configuración de puertos

Los puertos del host son configurables vía `.env.deploy` (raíz del repo).

| Variable | Default | Cambiar si... |
|----------|---------|---------------|
| `CADDY_HTTP_PORT` | `8080` | Tenés otra app dev en 8080 |
| `CADDY_HTTPS_PORT` | `8443` | Tenés otra app dev en 8443 |
| `POSTGRES_HOST_PORT` | `5432` | Tenés Postgres del sistema corriendo |
| `REDIS_HOST_PORT` | `6379` | Tenés Redis del sistema corriendo |

Antes de arrancar, ejecutá `check-ports` para verificar disponibilidad. Si
algún puerto está ocupado, te sugiere alternativas. `dev-up` lo invoca
automáticamente.

## Scripts de operación remota (placeholders Sprint 2+)

| Script | Propósito | Estado |
|--------|-----------|--------|
| `deploy.sh` | Roll out de nueva imagen/tag a entorno remoto | placeholder |
| `migrate.sh` | Alembic migrations con advisory lock | placeholder |
| `backup.sh` | `pg_dump` → cifrado con `age` → cross-provider (R2/B2) | placeholder |
| `restore.sh` | Restore desde backup cifrado | placeholder |
| `seed-roles.sh` | Seed RBAC roles + permisos (idempotente) | placeholder |

## Convenciones

- Secretos de prod vienen de **Doppler** runtime — nunca de `.env`. Wrappear con
  `doppler run --project mt-pricing --config <env> --`.
- Scripts deben ser **idempotentes** (run dos veces seguidas → mismo resultado).
- Logs van a **stdout** una línea por evento (parseable por Loki/Better Stack).
- Exit codes no-cero solo para fallos accionables (alerting hooks).

## Referencias

- ADR-034 — Hetzner + Docker Compose deploy strategy
- ADR-035 — Caddy reverse proxy (TLS + headers)
- ADR-049 — Alembic migration discipline
- ADR-050 — Terraform en Hetzner Cloud
- ADR-051 — Doppler para secrets
- `_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md`
