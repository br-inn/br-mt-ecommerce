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

## Performance — Directriz de Arquitectura

El servidor está en UAE (misma región que los usuarios, ~10-20ms RTT). Con latencia
baja, el cuello de botella es el **número de round-trips al DB** y el **volumen de
trabajo por request**, no la red. Estas reglas son **obligatorias** en todo código
nuevo o modificado.

### Backend

**1. Nunca queries secuenciales donde se puede usar subquery o JOIN.**
```python
# ❌ 2 round-trips al DB
model_id = (await session.execute(select(Product.model_id).where(...))).scalar()
rows = await session.execute(select(Cert).where(Cert.model_id == model_id))

# ✅ 1 round-trip
subq = select(Product.model_id).where(...).scalar_subquery()
rows = await session.execute(select(Cert).where(Cert.model_id == subq))
```

**2. `selectinload` para colecciones (N filas), `joinedload` para relaciones 1:1.**
```python
# ✅ Para listas (translations, assets): selectinload (evita cartesian product)
.options(selectinload(Product.translations), selectinload(Product.assets))

# ✅ Para objetos únicos (model, series): joinedload (1 query con JOIN)
.options(joinedload(Product.model))
```

**3. No añadir headers `Cache-Control` manualmente** — el `CacheControlMiddleware`
en `app/core/middleware.py` aplica `private, max-age=60` a todos los GET 200
automáticamente. Si un endpoint necesita TTL distinto, use `response.headers["Cache-Control"] = "..."`.

**4. `include_total=False` por defecto** en listados paginados. El COUNT es caro.
Solo activar cuando la UI lo muestra explícitamente.

### Frontend

**5. Imágenes — reglas obligatorias:**
```tsx
// Hero / above-the-fold (1 imagen por página)
<img src={url} fetchPriority="high" decoding="async" />

// Todas las demás (listas, grillas, thumbnails)
<img src={url} loading="lazy" decoding="async" />
```
Nunca `<img>` sin `loading` en listas. Usar `<Image>` de Next.js solo si se
necesita `srcset` automático (requiere `width` + `height` explícitos).

**6. React Query — `staleTime` mínimos por tipo de dato:**
| Tipo | staleTime |
|------|-----------|
| Detalle producto | 60 000 ms |
| Listados paginados | 30 000 ms |
| Vocabularios (series, materiales) | 300 000 ms |
| Datos de usuario/permisos | 0 (sin caché) |

**7. Nunca disparar N llamadas al API desde N componentes independientes** para el
mismo recurso. Usar un hook compartido con la misma `queryKey` — React Query
deduplica automáticamente a 1 request. Si los componentes necesitan datos
diferentes del mismo objeto, consolidar en un endpoint más rico o usar
`select` de React Query para proyectar.

**8. Páginas de detalle:** el primer render debe mostrar skeleton de inmediato.
No bloquear el render esperando datos. Cada sección carga su propio estado
de carga de forma independiente (`isLoading` por sección).
