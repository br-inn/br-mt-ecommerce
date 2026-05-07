# Onboarding — del `git clone` al primer PR mergeado en 1 día

Guía paso-a-paso para que un dev nuevo (BR o partner) llegue a:

1. Tener el stack corriendo localmente en **< 15 minutos**.
2. Entender la arquitectura y dónde vive cada cosa en **< 2 horas**.
3. Mergear su primer PR (ej: arreglar un typo, añadir un test) **el mismo
   día**.

---

## 1. Pre-requisitos (10 min)

Instalá en tu máquina:

| Herramienta | Versión | Notas |
|---|---|---|
| Git | ≥ 2.40 | — |
| Docker Desktop / Docker Engine | ≥ 24, Compose v2 | en Windows usar WSL2 |
| Node.js | 20 LTS | recomendado: `corepack enable` |
| pnpm | ≥ 9 | `corepack prepare pnpm@9 --activate` |
| Python | 3.11.x | exacto, no 3.12 (todavía) |
| uv | última | `pipx install uv` |
| Doppler CLI | última | opcional, para secretos compartidos |
| `make` | cualquiera | en Windows: vía WSL o Chocolatey |

Verificá:

```bash
git --version
docker --version && docker compose version
node --version && pnpm --version
python --version && uv --version
```

---

## 2. Acceso (5 min)

Pedí al tech lead (`psierra@br-innovation.com`):

- Permisos en el repo GitHub.
- Acceso al proyecto **Doppler** (`mt-pricing` con stage `dev_local`).
- Invitación al canal Slack #mt-platform.
- Si vas a tocar staging: credenciales temporales SSH a Hetzner staging.

---

## 3. Setup local (15 min)

```bash
# 3.1 Clonar
git clone <repo-url> br-mt-ecommerce
cd br-mt-ecommerce

# 3.2 Pre-commit hooks
pip install pre-commit
pre-commit install

# 3.3 Backend
cd mt-pricing-backend
cp .env.example .env
# Editar .env: si tenés Doppler, ejecutá `doppler setup` y `doppler run -- uv sync`
uv sync

# 3.4 Frontend
cd ../mt-pricing-frontend
cp .env.example .env.local
pnpm install

# 3.5 Levantar stack
cd ..
docker compose -f docker-compose.dev.yml up -d

# 3.6 Migrar y semillar DB
cd mt-pricing-backend
uv run alembic upgrade head
uv run python -m app.scripts.seed_initial
```

Verificá:

- `curl http://localhost:8000/healthz` → `200 ok`.
- `http://localhost:3000` → home del frontend renderiza.
- `docker compose -f docker-compose.dev.yml ps` → todos los servicios `healthy`.

Si algo falla, ver §6.

---

## 4. Tour del repo (1-2 h)

Leé en este orden:

1. [`README.md`](../../README.md) raíz — overview + estructura.
2. [`docs/architecture/README.md`](../architecture/README.md) — diagrama C4
   y patrones.
3. [`_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md`](../../_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md)
   — secciones que más te interesen.
4. [`docs/adr/README.md`](../adr/README.md) — escaneá la tabla de 54 ADRs;
   leé ADR-028 a ADR-035 + ADR-045 a ADR-054.
5. [`_bmad-output/planning-artifacts/sprint1-backlog-refined.md`](../../_bmad-output/planning-artifacts/sprint1-backlog-refined.md)
   — qué se está construyendo ahora.
6. [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — reglas de juego.

Recorré el código:

| Carpeta | Qué buscar |
|---|---|
| `mt-pricing-backend/app/main.py` | bootstrap FastAPI, middlewares |
| `mt-pricing-backend/app/api/v1/` | endpoints (un router por dominio) |
| `mt-pricing-backend/app/services/` | lógica de negocio (pricing, comparator, catalog) |
| `mt-pricing-backend/app/models/` | SQLAlchemy models |
| `mt-pricing-backend/alembic/versions/` | migraciones |
| `mt-pricing-frontend/app/` | rutas Next.js (App Router) |
| `mt-pricing-frontend/components/` | UI: `ui/` Shadcn raw, resto custom |
| `mt-pricing-frontend/lib/api/` | cliente API tipado |
| `infra/` | Terraform (Hetzner) |
| `supabase/` | migraciones supabase, RLS policies |

---

## 5. Tu primer PR (resto del día)

Buscá un issue con label `good-first-issue` o pedí uno al tech lead. Sugerencias:

- Añadir un test que falte en `app/services/<modulo>/`.
- Mejorar copy de un mensaje en `messages/es.json` y `messages/en.json`.
- Documentar un endpoint en el OpenAPI spec.
- Refactor pequeño marcado como TODO en código.

Workflow:

```bash
git checkout -b chore/<tu-nombre>-primer-pr
# trabajar...
cd mt-pricing-backend && uv run ruff check . && uv run pytest
cd ../mt-pricing-frontend && pnpm lint && pnpm test
git add <archivos>
git commit -m "chore: <descripcion>"  # commitlint validará
git push -u origin chore/<tu-nombre>-primer-pr
gh pr create --fill   # o usar UI de GitHub
```

Esperá review (≥ 1 approval) y CI verde, luego merge squash.

---

## 6. Troubleshooting

| Síntoma | Posible causa | Acción |
|---|---|---|
| `docker compose up` falla con `port already in use` | otro servicio usa 3000/8000/5432/6379 | `docker compose down` o cambiar puertos en `.env` |
| `alembic upgrade head` falla con `password authentication failed` | `DATABASE_URL` mal configurado en `.env` | revisar `mt-pricing-backend/.env.example` |
| Frontend devuelve `401 Unauthorized` en todo | falta seedear admin user | re-correr `uv run python -m app.scripts.seed_initial` |
| `pnpm install` falla en Windows nativo | path largos / symlinks | usar WSL2 |
| `uv sync` falla | versión de Python distinta a 3.11 | usar `pyenv` o `uv python install 3.11` |
| Caddy no monta TLS local | falta CA local | `caddy trust` o ignorar warning de certificado |
| Pre-commit hooks tardan mucho la primera vez | descargas de tools | normal: solo la primera ejecución |

Si nada funciona: pegale al tech lead en Slack con output completo.

---

## 7. Checklist de onboarding

Marcá cuando termines:

- [ ] Repo clonado y stack local corriendo (todos los servicios `healthy`).
- [ ] `curl http://localhost:8000/healthz` devuelve 200.
- [ ] Frontend renderiza login y podés autenticarte con el admin seed.
- [ ] Leí `README.md`, `CONTRIBUTING.md`, `docs/architecture/README.md`.
- [ ] Leí ADRs 028-035, 045-054.
- [ ] Conozco quién aprueba PRs y cómo correr lint/test.
- [ ] Mi primer PR está mergeado.
- [ ] Acceso a Doppler dev funcionando.
- [ ] Acceso a observabilidad (Grafana local) verificado.
