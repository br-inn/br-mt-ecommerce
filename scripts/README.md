# scripts/

Utilidades operativas del repo. Scripts diseñados para correr desde el root.

## `validate-e2e.ps1` / `validate-e2e.sh`

Orquestador de validación E2E para Sprint 1+2. Boot stack local → wait for
ready → run Playwright → teardown opcional.

### Quickstart

**Windows (pwsh):**

```powershell
# Run completo (boot + tests + teardown)
.\scripts\validate-e2e.ps1

# Solo healthchecks (smoke ~5s)
.\scripts\validate-e2e.ps1 -OnlyHealth

# Asume stack ya corriendo, solo run tests
.\scripts\validate-e2e.ps1 -SkipBoot

# Browser visible (debugging)
.\scripts\validate-e2e.ps1 -Headed -SkipBoot

# Deja stack arriba después
.\scripts\validate-e2e.ps1 -NoTeardown
```

**Linux/WSL/macOS:**

```bash
chmod +x scripts/validate-e2e.sh
./scripts/validate-e2e.sh
./scripts/validate-e2e.sh --only-health
./scripts/validate-e2e.sh --skip-boot --headed
./scripts/validate-e2e.sh --no-teardown
```

### Flags (paridad ps1 ↔ sh)

| pwsh           | bash             | efecto                                          |
| -------------- | ---------------- | ----------------------------------------------- |
| `-SkipBoot`    | `--skip-boot`    | NO arranca docker / supabase                    |
| `-NoTeardown`  | `--no-teardown`  | NO bajar la stack al terminar                   |
| `-Headed`      | `--headed`       | Playwright corre con browser visible            |
| `-OnlyHealth`  | `--only-health`  | Ejecuta solo `01-healthchecks.spec.ts`          |
| `-BootTimeoutSec N` | `--boot-timeout N` | Timeout wait-for-ready (default 60s)         |

### Exit codes

- `0` — todos los tests pasan
- `1` — algún test falla (Playwright)
- `2` — stack no booted (preflight o health timeout)

### Variables de entorno

- `E2E_BASE_URL` (default `http://localhost:8080`) — URL del frontend (Caddy single entry)
- `E2E_BACKEND_URL` (default = BASE_URL) — backend FastAPI; cuando uses Caddy, /api se proxy
- `E2E_USER_EMAIL`, `E2E_USER_PASSWORD` — credenciales para login real (default `e2e@mt.ae`)
- `E2E_USE_REAL_SUPABASE=1` — desactiva los `route()` mocks de Supabase auth

### Pre-requisitos

| comando      | propósito                           |
| ------------ | ----------------------------------- |
| `docker`     | docker compose dev stack            |
| `pnpm`       | paquetes frontend + Playwright CLI  |
| `node` 20+   | runtime                             |
| `python` 3.11+ | backend (solo si NO `-SkipBoot`)  |
| `uv` (opt.)  | bootstrap venv backend              |
| `supabase` (opt.) | local Supabase stack           |

### Diagnóstico

Si el script falla con exit 2 (stack no booted):

```bash
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs backend --tail=80
docker compose -f docker-compose.dev.yml logs frontend --tail=80
```

Para más detalle, ver [`docs/e2e-validation.md`](../docs/e2e-validation.md).
