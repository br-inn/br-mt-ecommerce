# E2E Test Users

Referencia de los usuarios que deben existir en Supabase Auth + `public.users`
para que el suite de Playwright corra correctamente contra el servidor real.

---

## Usuarios requeridos

| Email | Contraseña | Rol DB | Propósito |
|-------|-----------|--------|-----------|
| `e2e@mt.ae` | `Test1234!Test1234!` | `gerente_comercial` | Usuario genérico — Playwright impersona distintos roles via mocks de `/api/v1/me` |
| `e2e-admin@mt.ae` | `Test1234!Test1234!` | `admin` | Alternativo para tests que requieren permisos admin reales (sin mock) |

> **Nota de seguridad:** estas credenciales son públicas dentro del equipo.
> Los usuarios sólo existen en la instancia Supabase **de desarrollo / testing**,
> nunca en producción. El script de seed es idempotente — re-ejecutarlo es seguro.

---

## Crear / actualizar los usuarios

### Opción A — Desde dentro del contenedor Docker (dev local)

```bash
# Levantar el stack primero
docker compose -f docker-compose.dev.yml up -d

# Ejecutar seed
docker exec mt-backend python -m scripts.seed_e2e_users
```

### Opción B — uv local (sin Docker)

```bash
cd mt-pricing-backend

SUPABASE_URL=http://localhost:54321 \
SUPABASE_SERVICE_ROLE_KEY=<service_role_key_local> \
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:54322/postgres \
uv run python -m scripts.seed_e2e_users
```

### Opción C — Contra servidor remoto

```bash
cd mt-pricing-backend

SUPABASE_URL=<url_supabase_produccion_dev> \
SUPABASE_SERVICE_ROLE_KEY=<service_role_key> \
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>/<db> \
uv run python -m scripts.seed_e2e_users
```

El script es idempotente: si el usuario ya existe en Supabase Auth, actualiza
la contraseña y continúa. Si la fila `public.users` ya existe, sólo actualiza
el `role_id` si cambió.

---

## Ejecutar los tests E2E contra el servidor real

Una vez creados los usuarios, lanzar Playwright con `E2E_USE_REAL_SUPABASE=1`:

```bash
cd mt-pricing-frontend

# Servidor local (Docker dev)
E2E_BASE_URL=http://localhost:8081 \
E2E_USE_REAL_SUPABASE=1 \
pnpm test:e2e --project=chromium

# Servidor remoto (ej. 100.53.214.97)
E2E_BASE_URL=https://100-53-214-97.sslip.io \
E2E_BACKEND_URL=https://100-53-214-97.sslip.io \
E2E_USE_REAL_SUPABASE=1 \
pnpm test:e2e --project=chromium
```

### Variables de entorno de Playwright

| Variable | Default | Descripción |
|----------|---------|-------------|
| `E2E_BASE_URL` | `http://localhost:8080` | URL del frontend (Caddy) |
| `E2E_BACKEND_URL` | `$E2E_BASE_URL` | URL del backend; omitir si Caddy proxea `/api` y `/health` |
| `E2E_USE_REAL_SUPABASE` | `""` (false) | `"1"` para login real; `""` para mocks (solo funciona en dev local) |
| `E2E_USER_EMAIL` | `e2e@mt.ae` | Email del usuario de test |
| `E2E_USER_PASSWORD` | `Test1234!Test1234!` | Contraseña del usuario de test |
| `E2E_FLOWER_URL` | `http://localhost:5555` | URL de Flower (opcional; test se salta si no responde) |

---

## Por qué los mocks de auth no funcionan contra el servidor real

El suite usa por defecto mocks de Playwright que interceptan
`**/auth/v1/token**` y devuelven un JWT falso. Esto funciona en dev local
porque el Next.js SSR corre en la misma máquina (el dev server no valida el
JWT contra Supabase en cada request).

Contra un servidor real, Next.js valida la sesión **server-side** con el
secret de Supabase real → el JWT falso falla → el usuario es redirigido a
`/login`. Por eso se necesita `E2E_USE_REAL_SUPABASE=1` + usuario real.

---

## Roles en el sistema

Los roles disponibles en `public.roles` (códigos exactos de DB):

| Código DB | Nombre | Permisos principales |
|-----------|--------|---------------------|
| `comercial` | Comercial Canal Online | `products:read`, `prices:propose`, `matches:read/write` |
| `gerente_comercial` | Gerente Comercial | + `prices:approve`, `channels:manage`, `prices:override_review` |
| `ti_integracion` | TI Integración | + `users:*`, `channels:manage`, `graphrag:admin` |
| `admin` | Sysadmin | Todos los permisos anteriores |
| `auditor` | Auditor | `matches:read`, `channels:read` (solo lectura) |

> **Mapeo mocks ↔ DB:** Los test fixtures de Playwright usan códigos cortos
> (`gerente`, `ti`, `comercial`, `admin`). El usuario real en DB tiene rol
> `gerente_comercial`. Con mocks activos esto es irrelevante porque
> `/api/v1/me` se intercepta. Con `E2E_USE_REAL_SUPABASE=1` la respuesta real
> de `/api/v1/me` incluye `gerente_comercial`; el frontend lo maneja
> correctamente.

---

## Troubleshooting

### "User already registered" en seed

Normal — el script detecta el usuario existente, actualiza la contraseña y
sigue. Ver log `Supabase: password actualizada`.

### Tests redirigen a `/login` con `E2E_USE_REAL_SUPABASE=1`

1. Verificar que el seed corrió correctamente (`python -m scripts.seed_e2e_users`)
2. Confirmar que `E2E_USER_EMAIL` / `E2E_USER_PASSWORD` coinciden con los del seed
3. Intentar login manual en `E2E_BASE_URL/login` con las mismas credenciales
4. Revisar logs del backend (`docker logs mt-backend`) para ver si `/api/v1/me` devuelve 200

### "role not found" en seed

Las migraciones Alembic no están al día. Ejecutar:
```bash
docker exec mt-backend alembic upgrade head
# o
uv run alembic upgrade head
```
