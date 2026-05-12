# br-mt-ecommerce — Project Conventions

## Stack

- **Frontend**: Next.js 16 + React 19 + TypeScript estricto + Tailwind v4 + Shadcn/ui (new-york)
- **Backend**: FastAPI + Python 3.11 + Pydantic + Gunicorn/Uvicorn
- **ORM**: SQLAlchemy 2.0 async + Alembic (tablas `public.*`). supabase-py SOLO para Auth (`auth.admin.*`) y Storage
- **Worker**: Celery + Redis. Schedules en `public.job_definitions` — nunca hardcodear en `celery_config.py`
- **Auth**: Supabase Auth. App conecta como rol `mt_app` (NO `service_role` ni `anon`)
- **Storage**: Supabase Storage — bucket `product-images` obligatorio para imágenes
- **Deploy**: Hetzner + Docker Compose. NO Vercel, Prisma, Auth.js, BullMQ, R2, AWS

**Migrations split**: Alembic para `public.*`; Supabase migrations para `auth.*`/`storage.*`/RLS (aplicar Supabase primero, luego Alembic).

## Local Dev

- Supabase: `npx supabase start`
- Backend + Worker: `docker compose -f docker-compose.dev.yml up`
- Secrets: `.env.local` en cada subproyecto (no Doppler)
- Smoke tests contra `localhost:3000` (frontend) + `localhost:8000` (backend) + `localhost:54321` (supabase)

## Post-Change Deploy

Antes de reportar una tarea completa, redesplegar los contenedores afectados:

| Cambio | Comando |
|--------|---------|
| Frontend (código) | `docker restart mt-frontend` |
| Frontend (deps / Tailwind config) | `docker compose -f docker-compose.dev.yml up -d --build frontend` |
| Backend (código) | `docker restart mt-backend` |
| Worker / Beat | `docker restart mt-worker mt-beat` |
| Schema / migración | `./infra/scripts/migrate.sh` → `docker restart mt-backend` |

Verificar: `curl http://localhost:${CADDY_HTTP_PORT:-8081}/health/live`
