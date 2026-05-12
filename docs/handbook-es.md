# Manual Operativo — MT Middle East Pricing MDM

**Versión:** 1.0 — Sprint 7
**Mantenedor:** psierra@br-innovation.com
**Última actualización:** 2026-05-12
**Audiencia:** TI Integración MT + psierra (BR Innovation, on-call primario)

> Este manual es "wake-up-proof": si recibes una alerta a las 3am, puedes seguirlo sin pensar. Cada sección es auto-contenida. No necesitas leer otras secciones para ejecutar un runbook.

---

## Índice de contenido

1. [Visión general del sistema](#1-visión-general-del-sistema)
2. [Arranque y parada del sistema](#2-arranque-y-parada-del-sistema)
3. [Operaciones frecuentes](#3-operaciones-frecuentes)
4. [Workflow de aprobación de precios](#4-workflow-de-aprobación-de-precios)
5. [Troubleshooting — problemas frecuentes](#5-troubleshooting--problemas-frecuentes)
6. [Disaster Recovery](#6-disaster-recovery)
7. [Monitoreo y alertas](#7-monitoreo-y-alertas)
8. [Gestión de usuarios y permisos](#8-gestión-de-usuarios-y-permisos)
9. [Jobs y scheduler](#9-jobs-y-scheduler)
10. [Glosario](#10-glosario)

---

## 1. Visión general del sistema

### 1.1 Arquitectura en una página

```
                        ┌─────────────────────────────────────────────┐
                        │              Internet / UAE Users            │
                        └───────────────────┬─────────────────────────┘
                                            │ HTTPS
                        ┌───────────────────▼─────────────────────────┐
                        │         Caddy 2 — Reverse Proxy              │
                        │   TLS automático · Rate-limit · Routing      │
                        │   Prod: app.mtme.ae  /  Dev: localhost:8080  │
                        └────────┬──────────────────┬─────────────────┘
                                 │ /api/*            │ /*
              ┌──────────────────▼──┐          ┌────▼────────────────┐
              │  FastAPI (Python)   │          │  Next.js 16 SSR     │
              │  Puerto interno 8000│          │  Puerto interno 3000 │
              │  Gunicorn + Uvicorn │          │  App Router + RSC   │
              └──────┬────┬────────┘          └────────────────────┘
                     │    │
         ┌───────────┘    └──────────────────────────────┐
         │                                               │
┌────────▼──────────┐                       ┌────────────▼──────────┐
│  Supabase Postgres │                       │        Redis 7        │
│  (Cloud — UAE)     │                       │  Broker Celery (db 1) │
│  RLS + pgvector    │                       │  Result backend (db 2)│
│  uuidv7 + partición│                       │  Cache / FX (db 0)   │
└────────────────────┘                       └────────────┬──────────┘
                                                          │
                                             ┌────────────▼──────────┐
                                             │  Celery Workers        │
                                             │  6 queues nombradas   │
                                             │  + Celery Beat        │
                                             └───────────────────────┘
                        ┌─────────────────────────────────────────────┐
                        │          Supabase Storage (Cloud)            │
                        │  product-images · product-datasheets         │
                        │  import-batches · exports · thumbnails       │
                        └─────────────────────────────────────────────┘
```

### 1.2 Componentes principales

| Componente | Tecnología | Rol |
|------------|-----------|-----|
| **API Backend** | FastAPI 0.x / Python 3.11 / Pydantic / SQLAlchemy 2.0 async | Lógica de negocio, pricing engine, workflow de aprobación |
| **Frontend** | Next.js 16 / React 19 / TypeScript / Tailwind v4 / Shadcn/ui | Interfaz web MT Middle East |
| **Worker Celery** | Celery 5 / 6 queues nombradas | Imports masivos, recálculo precios, imágenes, comparador, notificaciones |
| **Beat Scheduler** | Celery Beat / DatabaseScheduler (ADR-046) | Cron jobs editables sin redeploy desde BD |
| **Base de datos** | Supabase Postgres (pgvector + RLS + particionado) | Fuente de verdad — audit trail, precios, productos |
| **Cache / Queue** | Redis 7 Alpine | Broker Celery, cache FX, embeddings, rate-limit |
| **Storage** | Supabase Storage | Imágenes, fichas técnicas, exports |
| **Reverse proxy** | Caddy 2 | TLS, routing, rate-limit |
| **Auth** | Supabase Auth (JWT) | Autenticación usuarios; RLS en BD por rol |
| **ORM / Migrations** | SQLAlchemy 2.0 + Alembic | Gestión esquema Postgres |

### 1.3 URLs de acceso

| Entorno | URL | Notas |
|---------|-----|-------|
| **Producción** | `https://app.mtme.ae` | Hetzner Frankfurt (CX22) + Caddy TLS |
| **Status page** | `https://status.mtme.br-innovation.com` | Better Stack Status (password protegida Fase 1) |
| **Dev local** | `http://localhost:8080` | Caddy en Docker Compose dev |
| **API docs (dev)** | `http://localhost:8080/api/docs` | Swagger UI (deshabilitado en prod) |
| **Redis (dev)** | `localhost:6379` | Acceso directo IDE/CLI |
| **Grafana Cloud** | `https://grafana.com` (org BR Innovation) | Dashboards operativos |
| **Sentry** | `https://sentry.io/organizations/br-innovation/` | Error tracking |
| **Better Stack Logs** | `https://logs.betterstack.com` | Logs centralizados |

### 1.4 Stack de herramientas operativas

| Herramienta | Propósito | Dónde mirar primero |
|-------------|-----------|---------------------|
| **Sentry** | Errores y excepciones tiempo real | Issue list → Project `mt-api` |
| **Grafana Cloud** | Métricas, dashboards, SLO burn rate | Dashboard "Service Health" |
| **Better Stack Logs** | Logs estructurados centralizados (30d hot, 90d cold) | Search por `service:mt-api` |
| **Better Stack Status** | Uptime y on-call | `status.mtme.br-innovation.com` |
| **Supabase Console** | BD, Auth, Storage, PITR | `supabase.com/dashboard` |
| **Hetzner Console** | Servidor VPS, disco, snapshots | `console.hetzner.com` |
| **Doppler** | Secretos y variables de entorno | `dashboard.doppler.com` |
| **Cloudflare** | DNS, certificados (prod) | `dash.cloudflare.com` |

---

## 2. Arranque y parada del sistema

### 2.1 Entorno local (desarrollo)

El stack local usa `docker-compose.dev.yml`. La base de datos y Auth/Storage apuntan a Supabase real (cloud). Redis es local dockerizado.

**Pre-requisitos:**
- Docker Desktop corriendo
- Supabase CLI instalado (`supabase start` no requerido — usamos cloud)
- Archivo `mt-pricing-backend/.env` con las variables de entorno locales
- Archivo `mt-pricing-frontend/.env.local` con variables del frontend

**Variables de entorno mínimas en `mt-pricing-backend/.env`:**

```bash
# Base de datos (Supabase pooler — usa transaction pool para async)
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[pass]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres

# Supabase
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_ANON_KEY=[anon-key]
SUPABASE_SERVICE_ROLE_KEY=[service-role-key]

# Redis (en dev: docker interno)
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# App
ENV=development
TIMEZONE=Asia/Dubai
APP_URL=http://localhost:8080

# Observabilidad (opcional en dev)
SENTRY_DSN=https://[key]@sentry.io/[project-id]

# SMTP digest diario (opcional en dev)
SMTP_ENABLED=false
```

### 2.2 Orden de arranque correcto

⚠️ El orden importa. Celery necesita Redis arriba antes de conectarse.

```bash
# Desde la raíz del repositorio: C:\BR-Github\br-mt\br-mt-ecommerce\
# (o /ruta/al/repo/ en Linux/Mac)

# 1. Arrancar todo el stack
docker compose -f docker-compose.dev.yml up -d

# 2. Verificar que todos los servicios están saludables
docker compose -f docker-compose.dev.yml ps
```

El orden de inicio gestionado por Docker Compose (via `depends_on`):

```
Redis → Backend (FastAPI) → Frontend (Next.js)
      → Worker (Celery)
      → Beat (Celery Beat)
      → Caddy (entry point)
```

### 2.3 Verificar que todo está OK

```bash
# Healthcheck liveness (event loop responde)
curl http://localhost:8080/health/live
# Respuesta esperada: {"status":"ok","ts":1715000000.0}

# Healthcheck readiness (DB + Redis + Supabase)
curl http://localhost:8080/health/ready
# Respuesta esperada: {"status":"ok","checks":{"db":"ok","redis":"ok","supabase":"ok"}}

# Ver logs en tiempo real
docker compose -f docker-compose.dev.yml logs -f backend worker beat

# Ver estado de contenedores
docker compose -f docker-compose.dev.yml ps
```

✅ El sistema está OK cuando:
- `health/live` responde `{"status":"ok"}`
- `health/ready` responde `{"status":"ok"}` con todos los checks en `"ok"`
- `docker compose ps` muestra todos los contenedores como `healthy`

### 2.4 Parada del sistema

```bash
# Parar todos los servicios (sin borrar datos)
docker compose -f docker-compose.dev.yml down

# Parar Y borrar cache Redis (útil si la queue está corrupta)
docker compose -f docker-compose.dev.yml down -v

# Parar un servicio individual (sin afectar el resto)
docker compose -f docker-compose.dev.yml stop worker
docker compose -f docker-compose.dev.yml stop beat
```

---

## 3. Operaciones frecuentes

### 3.1 Deploy de nueva versión

**En producción (path normal CI/CD):**

El deploy ocurre automáticamente cuando se hace merge a `main` y el CI (GitHub Actions) está verde. El workflow `deploy-prod.yml` se encarga de todo.

**Deploy manual (si CI falla o se requiere urgencia):**

```bash
# 1. Conectarse al servidor Hetzner
ssh deploy@app.mtme.ae

# 2. Ir al directorio de la aplicación
cd /opt/mt

# 3. Actualizar código e imágenes
git pull
docker compose pull

# 4. Desplegar sin downtime (--no-deps evita recrear dependencias)
docker compose up -d --no-deps api worker beat

# 5. Esperar que los healthchecks estén verdes
sleep 15
curl https://app.mtme.ae/health/ready

# 6. Notificar en Slack #mt-ops
echo "Deploy [$(git rev-parse --short HEAD)] OK - $(date)"
```

✅ Verificación post-deploy: Sentry sin spike de errores en los primeros 5 minutos.

⚠️ Si el deploy falla → ir a §3.2 Rollback.

### 3.2 Rollback de migración Alembic

⚠️ Sólo hacer rollback si la migración es **reversible**. Verificar el archivo de migración antes de ejecutar.

```bash
# 1. Conectar al servidor
ssh deploy@app.mtme.ae
cd /opt/mt

# 2. Ver la revisión actual
docker compose exec api alembic current
# Ejemplo de salida: abc123def456 (head)

# 3. Ver el historial reciente
docker compose exec api alembic history --verbose -r -3:current

# 4. Rollback de la última migración
docker compose exec api alembic downgrade -1

# 5. Si necesitas bajar a una revisión específica
docker compose exec api alembic downgrade abc123def456

# 6. Verificar que quedó en la revisión esperada
docker compose exec api alembic current
```

⚠️ Si la migración NO es reversible (down_revision vacío o elimina datos):
- No usar `downgrade`
- Activar `READ_ONLY_MODE=true`
- Restaurar desde PITR de Supabase (ver §6 DR-02)

### 3.3 Restart de workers Celery

```bash
# Restart de worker (si está zombie o no procesa tasks)
docker compose -f docker-compose.dev.yml restart worker

# En producción
ssh deploy@app.mtme.ae
cd /opt/mt
docker compose restart worker

# Restart solo del Beat scheduler
docker compose restart beat

# Verificar que el worker arrancó y está procesando
docker compose logs -f worker --tail=50

# Verificar workers activos via Celery inspect
docker compose exec worker celery -A app.workers.worker inspect active
```

### 3.4 Limpiar cola Redis

```bash
# Ver tamaño de cada queue
docker compose exec redis redis-cli LLEN celery        # queue default
docker compose exec redis redis-cli LLEN imports
docker compose exec redis redis-cli LLEN pricing
docker compose exec redis redis-cli LLEN images
docker compose exec redis redis-cli LLEN comparator
docker compose exec redis redis-cli LLEN notifications
docker compose exec redis redis-cli LLEN audit

# Ver las primeras 5 tasks en una queue
docker compose exec redis redis-cli LRANGE celery 0 4

# Limpiar una queue específica (⚠️ operación destructiva — los tasks se pierden)
docker compose exec redis redis-cli DEL pricing

# Limpiar TODAS las queues (⚠️ muy destructivo — usar solo en emergencia)
docker compose exec redis redis-cli FLUSHDB
```

⚠️ Antes de limpiar una queue, identifica qué tasks contiene y si son reproducibles.

### 3.5 Cargar Excel de referencia para parallel run

El parallel run compara precios de la app contra una tabla de referencia cargada desde Excel.

```bash
# API endpoint para cargar el Excel de referencia
# Requiere autenticación con rol ti_integracion o admin

curl -X POST https://app.mtme.ae/api/v1/parallel-run/upload \
  -H "Authorization: Bearer [JWT_TOKEN]" \
  -F "file=@/ruta/al/archivo.xlsx"

# Verificar que la carga fue exitosa
curl https://app.mtme.ae/api/v1/parallel-run/report?date=$(date +%Y-%m-%d) \
  -H "Authorization: Bearer [JWT_TOKEN]"
```

**Desde la UI:**
1. Ir a `app.mtme.ae` → Menú → Parallel Run
2. Click "Cargar Excel de referencia"
3. Seleccionar archivo (formato `.xlsx`, columnas: SKU, canal, precio_ref)
4. Click "Importar"
5. Verificar en la tabla que los precios de referencia aparecen correctamente

### 3.6 Gestión de FX rates (carga manual)

Los FX rates se actualizan automáticamente desde el feed externo. Si el feed falla, se carga manualmente.

```bash
# Ver FX rates actuales
curl https://app.mtme.ae/api/v1/fx-rates \
  -H "Authorization: Bearer [JWT_TOKEN]"

# Cargar rate manual (requiere permiso fx:manage — rol ti_integracion o admin)
curl -X POST https://app.mtme.ae/api/v1/fx-rates \
  -H "Authorization: Bearer [JWT_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{
    "currency_pair": "USD_AED",
    "rate": 3.6725,
    "valid_from": "2026-05-12T00:00:00Z",
    "source": "manual_central_bank_uae",
    "manual_override": true
  }'
```

**Via SQL directo (si la API no está disponible):**

```sql
-- Conectar a Supabase Console → SQL Editor
INSERT INTO fx_rates (currency_pair, rate, valid_from, source, manual_override)
VALUES ('USD_AED', 3.6725, now(), 'manual_central_bank_uae', true);

-- Verificar que se insertó correctamente
SELECT * FROM fx_rates WHERE currency_pair = 'USD_AED' ORDER BY valid_from DESC LIMIT 5;
```

⚠️ Notificar a Christian (Gerente) cuando se usa override manual de FX (riesgo de audit).

### 3.7 Activar/desactivar feature flags

Los feature flags controlan funcionalidades sin necesidad de redeploy.

```bash
# Listar todos los flags y sus valores
curl https://app.mtme.ae/api/v1/admin/flags \
  -H "Authorization: Bearer [JWT_TOKEN]"

# Activar un flag (requiere permiso flags:manage — ti_integracion o admin)
curl -X PATCH https://app.mtme.ae/api/v1/admin/flags/comparator.enabled \
  -H "Authorization: Bearer [JWT_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Desactivar un flag
curl -X PATCH https://app.mtme.ae/api/v1/admin/flags/comparator.enabled \
  -H "Authorization: Bearer [JWT_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

**Via SQL directo:**

```sql
-- Activar flag
UPDATE feature_flags SET value='true', updated_at=now() WHERE key='comparator.enabled';

-- Desactivar flag
UPDATE feature_flags SET value='false', updated_at=now() WHERE key='comparator.enabled';

-- Throttle de LLM (reducir concurrencia)
UPDATE feature_flags SET value='5' WHERE key='comparator.max_concurrent_llm_calls';

-- Activar modo lectura (escrituras bloqueadas — usar en emergencia o mantenimiento)
UPDATE feature_flags SET value='true' WHERE key='READ_ONLY_MODE';
```

**Kill switch de emergencia (desactiva todos los features no críticos):**

```bash
curl -X POST https://app.mtme.ae/api/v1/admin/flags/kill-switch \
  -H "Authorization: Bearer [JWT_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"engage": true, "reason": "Emergency maintenance"}'
```

---

## 4. Workflow de aprobación de precios — guía operativa

### 4.1 Ciclo de vida de un precio

```
  DRAFT
    │
    │  POST /pricing/prices  (comercial propone)
    │
    ▼
  PENDING_REVIEW ──── dentro de tolerancia ────► AUTO_APPROVED
    │                                                  │
    │  Gerente revisa (UI o API)                       │
    ├─────────────────────────────────────────────►  APPROVED
    │  approve                                         │
    │                                                  │
    ├── reject ──────────────────────────────────► REJECTED
    │                 (vuelve a DRAFT para revisar)
    │
    │  > 48h sin acción → escalation worker
    │
    ▼
  ESCALATED (flag en el precio, notificación al Gerente)
```

**Transiciones y quién las ejecuta:**

| Transición | Actor | Endpoint |
|-----------|-------|----------|
| draft → pending_review | TI Integración / Sistema | `POST /pricing/prices` |
| pending_review → auto_approved | Sistema (dentro de tolerancia) | Automático |
| pending_review → approved | Gerente Comercial | `POST /pricing/prices/{id}/approve` |
| pending_review → rejected | Gerente Comercial | `POST /pricing/prices/{id}/reject` |
| rejected → pending_review | TI Integración (revisa monto) | `POST /pricing/prices/{id}/revise` |
| approved → exported | Sistema / TI | `POST /pricing/prices/{id}/export` |

### 4.2 Precios atascados en pending_review

Si hay precios que llevan más de 24h en `pending_review`:

```bash
# 1. Identificar precios atascados
# Via SQL (Supabase Console → SQL Editor):
SELECT
    p.id,
    p.sku,
    p.channel,
    p.amount_aed,
    p.state,
    p.created_at,
    now() - p.created_at AS tiempo_esperando
FROM prices p
WHERE p.state = 'pending_review'
  AND p.created_at < now() - interval '24 hours'
ORDER BY p.created_at ASC;

# 2. Verificar si el Gerente recibió la notificación del digest
# (ver logs Better Stack con filtro: event:pricing.daily_digest)

# 3. Si el Gerente no recibió notificación → ejecutar digest manualmente (ver §9)
```

### 4.3 Bulk-approve manual via API

Usar cuando el Gerente necesita aprobar múltiples precios de una vez:

```bash
# Aprobar múltiples precios por IDs
curl -X POST https://app.mtme.ae/api/v1/pricing/prices/bulk-approve \
  -H "Authorization: Bearer [JWT_TOKEN_GERENTE]" \
  -H "Content-Type: application/json" \
  -d '{
    "price_ids": [
      "uuid-precio-1",
      "uuid-precio-2",
      "uuid-precio-3"
    ],
    "comment": "Aprobación batch semana 20"
  }'
```

⚠️ Solo el Gerente Comercial (rol `gerente_comercial`) puede ejecutar bulk-approve.

### 4.4 Cómo interpretar el digest diario 18:00 UAE

El digest se envía automáticamente cada día a las 18:00 hora UAE (14:00 UTC) a todos los usuarios con rol `gerente_comercial`.

**Estructura del digest:**

| Campo | Significado | Acción si preocupa |
|-------|------------|-------------------|
| `pending_review` | Precios esperando aprobación del Gerente | > 5 → revisar esa misma tarde |
| `auto_approved` | Aprobados automáticamente (dentro de tolerancia) | Normal, no requiere acción |
| `approved` | Aprobados manualmente hoy | Información |
| `escalated` | Llevan > 48h sin decisión (⚠️ alerta) | Acción inmediata |
| `total` | Total de precios procesados hoy | Referencia |

**Re-ejecutar el digest manualmente:**

```bash
# Via API (requiere permiso admin)
curl -X POST https://app.mtme.ae/api/v1/admin/tasks/daily-digest \
  -H "Authorization: Bearer [JWT_ADMIN_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"target_date": "2026-05-12"}'

# Via Celery (desde el servidor)
ssh deploy@app.mtme.ae
cd /opt/mt
docker compose exec worker celery -A app.workers.worker call \
  mt.pricing.daily_digest \
  --args='["2026-05-12"]'
```

---

## 5. Troubleshooting — problemas frecuentes

| Síntoma | Causa probable | Diagnóstico | Solución |
|---------|---------------|-------------|---------|
| **App no carga, browser timeout** | Servidor Hetzner caído o Caddy no inicia | `curl -k https://[hetzner-ip]/health/live` — si falla, SSH al servidor | Reboot via Hetzner Console (ver DR-01 en §6) |
| **API devuelve 503 en /health/ready** | Postgres o Redis no accesibles | `curl .../health/db` y `/health/redis` con X-Health-Token | Ver logs backend: `docker compose logs backend --tail=50` |
| **Worker no procesa tasks (queue crece)** | Worker zombie, crash loop, task larga atascada | `docker compose exec worker celery -A app.workers.worker inspect active` | Restart worker: `docker compose restart worker` (ver §3.3) |
| **FX rates desactualizados (alerta `fx_rate_age_hours > 25`)** | Feed externo caído o rate limit | `curl https://[fx-feed-url]` para verificar disponibilidad | Carga manual de FX (ver §3.6) |
| **Precios no se calculan / error pricing engine** | Falta FX rate activo para el par de monedas requerido | Query: `SELECT * FROM fx_rates WHERE is_active=true ORDER BY valid_from DESC LIMIT 10;` | Insertar FX rate manual (ver §3.6) |
| **Importación de Excel falla (batch stuck en "processing")** | Worker crasheó durante el proceso | `SELECT id, state, started_at, error_msg FROM import_batches WHERE state='processing';` | Force-fail el batch (ver §5.1) |
| **Migración Alembic falla en deploy** | Conflicto de heads o tabla inexistente | `docker compose exec api alembic history --verbose` — ver qué revisión falla | Rollback: `alembic downgrade -1` (ver §3.2); si no reversible, usar PITR (ver §6) |
| **Error rate spike en Sentry post-deploy** | Bug en el código nuevo | Sentry → Project mt-api → Issues → filtrar por `last_seen: last hour` | Rollback de deploy (ver §3.2 imagen anterior) |
| **Disco Hetzner > 85%** | Logs, imágenes Docker, o datos sin limpiar | `ssh deploy@app.mtme.ae && df -h` | `docker system prune -af && journalctl --vacuum-time=7d` |
| **Login usuarios falla (Supabase Auth)** | Token expirado, cuenta bloqueada, o outage Supabase | Verificar `https://status.supabase.com`; Supabase Console → Auth → Users | Unlock usuario (ver §8.3); si outage → activar `READ_ONLY_MODE=true` |
| **Digest diario no llegó** | SMTP deshabilitado, Celery Beat caído, o task fallida | `docker compose logs beat --tail=50`; Sentry → `mt.pricing.daily_digest` | Restart beat, ejecutar digest manual (ver §4.4) |
| **Parallel run report vacío o desactualizado** | Task `parallel_run_diff` no corrió o Excel de referencia no cargado | Verificar en Better Stack Logs: `task_name:mt.pricing.parallel_run_diff` | Cargar Excel de referencia (ver §3.5); ejecutar task manualmente |
| **Precios escalados no se notificaron** | Tarea `mt.pricing.escalate_pending` no corrió | `docker compose logs beat` → buscar `escalate_pending` | Restart beat; ejecutar escalación manual vía Celery |
| **Grafana dashboards sin datos** | Prometheus no scrape, o remote_write a Grafana Cloud fallando | `curl localhost:9090/metrics` en Hetzner; ver targets en `localhost:9090/targets` | Restart prometheus: `docker compose restart prometheus` |

### 5.1 Force-fail de import batch huérfano

```sql
-- 1. Identificar batch atascado (Supabase Console → SQL Editor)
SELECT id, source_file, started_at, state
FROM import_batches
WHERE state = 'processing'
  AND started_at < now() - interval '2 hours';

-- 2. Force-fail (reemplazar [batch-uuid] con el ID real)
UPDATE import_batches
SET
    state = 'failed',
    error_msg = 'timeout — force-failed by ops',
    failed_at = now()
WHERE id = '[batch-uuid]';

-- 3. Verificar
SELECT id, state, error_msg FROM import_batches WHERE id = '[batch-uuid]';
```

---

## 6. Disaster Recovery

**Objetivos:**
- **RTO global: 4 horas** (tiempo máximo para restaurar el servicio)
- **RPO global: 1 hora** (máxima pérdida de datos tolerable)
- **SLA horario laboral GCC (08:00–18:00 GST, L–V): 99.5%**

### 6.1 DR-01 — Fallo total servidor Hetzner

**Síntomas:** `https://app.mtme.ae` no responde, SSH falla, Better Stack alerta ping fallido > 5 min.

**Pasos:**

1. Confirmar que NO es DNS o Caddy — probar IP directa:
   ```bash
   curl -k https://[HETZNER_IP]/health/live
   ```

2. Login en Hetzner Cloud Console → ver estado del servidor.

3. Si servidor "running" pero unreachable → **forzar reboot** vía botón "Power" en consola. Esperar 3 min.

4. Si reboot no resuelve → **provisionar servidor alternativo** (Helsinki si Frankfurt caído):
   ```bash
   bash scripts/provision_dr_server.sh --region hel1 --type cx22
   ```

5. Postgres está en Supabase (independiente de Hetzner) — no requiere acción.

6. Apuntar DNS Cloudflare `app.mtme.ae` al IP nuevo (TTL 60s pre-configurado).

7. Pull y levantar stack:
   ```bash
   cd /opt/mt
   git pull
   doppler run -- docker compose -f docker-compose.prod.yml up -d
   ```

8. Verificar:
   ```bash
   curl https://app.mtme.ae/health/ready
   # Esperado: {"status":"ok"}
   ```

9. Smoke test: login con cuenta de prueba, ver lista de productos.

**Comunicar en Slack `#mt-status`:**
```
[SEV1] [DR-01] Servidor app.mtme.ae caído desde HH:MM GST.
Causa: hardware fail Hetzner.
ETA recuperación: 2h.
Workaround: ninguno.
Owner: @pablo. Próxima update: en 30 min.
```

### 6.2 DR-02 — Corrupción de base de datos

**Síntomas:** Usuarios reportan "faltan productos" o "precios desaparecieron". Sentry: spike 5xx con `relation does not exist` o nulls inesperados.

**Pasos:**

1. **CONGELAR ESCRITURAS INMEDIATO:**
   ```bash
   docker compose stop api worker
   ```

2. Identificar T0 (momento previo al problema) desde audit log:
   ```sql
   SELECT actor, count(*), min(occurred_at), max(occurred_at)
   FROM audit_events
   WHERE action = 'delete'
     AND occurred_at > now() - interval '1 hour'
   GROUP BY actor ORDER BY count DESC;
   ```

3. Ir a **Supabase Console → Project → Database → Backups → Restore to point in time**.

4. Seleccionar T0 menos 1 minuto.

5. ⚠️ Primero crear **branch** del proyecto en Supabase (evitar pérdida adicional durante restauración).

6. Validar el branch restaurado:
   ```sql
   -- En el branch restaurado:
   SELECT count(*) FROM products;
   SELECT count(*) FROM prices WHERE state = 'approved';
   SELECT max(created_at) FROM audit_events;
   ```

7. Si datos OK → promote branch a proyecto principal (Supabase UI).

8. Reiniciar servicios:
   ```bash
   docker compose start api worker
   ```

9. Smoke test completo.

**Comunicar (Slack `#mt-status` + email a Christian/Paula):**
```
[SEV1] [DR-02] Detectada corrupción/borrado en Postgres a las HH:MM.
Acción: escrituras congeladas, ejecutando PITR a T0.
ETA: 30 min.
Owner: @pablo
```

### 6.3 DR-03 — Credenciales comprometidas

**Síntomas:** Login geo-anómalo en Better Stack, email "new device login" de Hetzner/Supabase, comportamiento sospechoso (tasks no programadas, secretos cambiados).

**Pasos:**

1. ⚠️ **NO borrar evidencia** — capturar screenshots de dashboards y audit logs primero.

2. **Rotar TODOS los secretos:**
   - Supabase → API → Reset service role key y anon key
   - Hetzner → rotar API token + cambiar password + activar MFA
   - Doppler → rotar service token
   - Cloudflare → rotar API token
   - GitHub → revocar PATs y deploy keys

3. **Force logout todos los usuarios:**
   ```sql
   -- Supabase Console → SQL Editor
   UPDATE auth.users
   SET raw_app_meta_data = raw_app_meta_data || '{"force_logout_at":"NOW"}';
   ```

4. Revisar `audit_events` de las últimas 72h buscando actores no esperados.

5. Redeploy con nuevos secretos: `doppler run -- docker compose -f docker-compose.prod.yml up -d`.

**Comunicar (email Christian/Paula + Slack `#mt-status`):**
```
[SEV1] [DR-05] Posible account compromise detectado a HH:MM.
Acción: secretos rotados, force-logout all, investigando scope.
Compliance: si hay exfiltración confirmada, notificar UAE PDPL en 72h.
Owner: @pablo + TI MT
```

### 6.4 DR-04 — Worker Celery stuck (toda la queue)

**Síntomas:** Queue size > 1000 y no desciende (alerta Better Stack), tasks no procesadas en > 30 min.

**Pasos:**

1. Ver tasks activas:
   ```bash
   docker compose exec worker celery -A app.workers.worker inspect active
   ```

2. Si una task lleva > 30 min → identificar su `task_id` en el output anterior.

3. Terminar la task bloqueante:
   ```bash
   docker compose exec worker celery -A app.workers.worker control revoke [TASK_ID] --terminate --signal=SIGKILL
   ```

4. Si el worker entero está zombie → restart:
   ```bash
   docker compose restart worker
   ```

5. Verificar que la queue desciende:
   ```bash
   docker compose exec redis redis-cli LLEN pricing
   ```

6. Si la queue sigue creciendo → scale workers temporalmente:
   ```bash
   # Editar docker-compose.prod.yml: worker → deploy: replicas: 4
   docker compose up -d worker
   ```

### 6.5 Cuándo escalar al sponsor

**Escalar a Christian (sponsor MT) cuando:**
- Sistema completamente caído > 2 horas sin resolución (SEV1)
- Pérdida de datos confirmada (cualquier cantidad)
- Possible account compromise (DR-03)
- Outage de Supabase > 4 horas
- Error budget mensual consumido al 100% (reunión requerida)

**Contacto:**
- Christian: contacto via canal Slack `#mt-oncall` (privado)
- Paula (validador técnico): contacto backup para decisiones técnicas críticas

**Escalation automática (via Better Stack On-call):**
```
Alerta → Pablo Sierra (5 min ack window)
       ↓ no ack
       TI MT Integración (10 min ack window)
       ↓ no ack
       Christian (escalation manager)
```

---

## 7. Monitoreo y alertas

### 7.1 Qué mirar en Sentry

**URL:** `https://sentry.io/organizations/br-innovation/` → Project `mt-api`

| Qué mirar | Cómo interpretarlo | Cuándo actuar |
|-----------|-------------------|--------------|
| **Issue list** (ordenar por "Last seen") | Errores nuevos aparecen primero | Si hay un issue con > 10 eventos en la última hora |
| **Error rate** (gráfico top del dashboard) | Línea plana = normal; spike = problema | Spike > 5x del baseline → investigar |
| **Releases** | Cada deploy crea una release en Sentry | Si un spike coincide con una release → rollback |
| **Performance** | Latencia por endpoint | p95 > 500ms sostenido = acción |

**Alertas configuradas en Sentry:**

| Alerta | Condición | Canal |
|--------|-----------|-------|
| Spike de errores | Error rate > 1% por 5 min | Slack `#mt-alerts` + on-call |
| Issue nuevo | First seen en última hora | Slack `#mt-alerts` |
| Regresión release | Issue resuelto reaparece en nueva release | Slack + email |
| Performance regression | p95 transaction +50% vs release anterior | Slack `#mt-alerts` |

### 7.2 Qué mirar en Grafana

**URL:** Grafana Cloud → Org BR Innovation → Dashboards → MT Pricing MDM

**6 dashboards principales:**

| Dashboard | Cuándo mirarlo | Métricas clave |
|-----------|---------------|----------------|
| **1. Service Health** | Siempre — primer dashboard a abrir | RPS, p95 latency, error rate 4xx/5xx, CPU/RAM |
| **2. Celery Health** | Si hay reports de tasks lentas | Queue depth por queue, task success/failure rate, task duration p95 |
| **3. Database Health** | Si hay queries lentas o errores 503 | Connections vs pool size, slow queries (>200ms), replication lag |
| **4. Business KPIs** | Daily review (9am GST) | Precios pending_review, auto-approve rate, approval latency p95 |
| **5. Cost Dashboard** | Semanal o si hay alerta de budget | LLM calls/día, USD acumulado, Hetzner usage |
| **6. Error Budget** | Semanal o incidente SEV1 | SLO compliance %, burn rate 1h/6h/24h |

### 7.3 Umbrales de alerta y qué significan

| Alerta | Umbral | Severidad | Qué hacer |
|--------|--------|-----------|-----------|
| Backend error rate alto | > 1% por 5 min | P1 | Ver Sentry → identificar endpoint → rollback o feature flag off |
| Celery queue depth | > 500 tasks por 10 min | P1 | Restart worker o escalar replicas (§3.3) |
| Postgres pool saturation | > 80% conexiones usadas | P1 | Ver queries lentas en Supabase Console; restart API si necesario |
| Disk Hetzner | < 20% libre | P1 | `docker system prune -af`; si < 5% → resize urgente |
| Redis memory | > 80% | P2 | Ver qué keys ocupan: `redis-cli MEMORY DOCTOR` |
| Failed logins | > 5/min | P2 (seguridad) | Ver IPs en Sentry → bloquear en Cloudflare si necesario |
| FX rate desactualizado | > 25h sin actualizar | P2 | Carga manual FX (§3.6) |
| Approval queue stale | p95 > 48h sin decisión | P3 | Notificar Gerente Comercial |
| SLO burn rate | > 14.4× en 1h | P0 | Alerta máxima — SMS + on-call + SEV1 |
| Backup integrity fallo | Verify semanal falla | P1 | Investigar logs backup; escalate DR-02 si datos comprometidos |

### 7.4 On-call: quién llama a quién

| Nivel | Persona | Rol | Disponibilidad |
|-------|---------|-----|----------------|
| **Primario** | Pablo Sierra (psierra@br-innovation.com) | BR Innovation, on-call principal | Horario laboral GCC L–V |
| **Secundario** | TI Integración MT | Backup primario | Horario laboral GCC |
| **Escalation manager** | Christian (sponsor MT) | Sólo SEV1 | On-call business hours |
| **Domain expert** | Gerente Comercial (Paula) | Decisiones negocio en SEV1 funcional | Horario laboral |

**Canales Slack:**
- `#mt-alerts` — alertas ops automáticas
- `#mt-status` — comunicación de incidentes (visible equipo MT)
- `#mt-oncall` — rotación on-call (privado)
- `#mt-ops` — logs operativos y deploys

---

## 8. Gestión de usuarios y permisos

### 8.1 Roles del sistema

| Rol (code) | Descripción | Permisos principales |
|-----------|-------------|---------------------|
| `admin` | Administrador del sistema | Todos los permisos, incluye `flags:manage`, `kill-switch:execute`, `users:*` |
| `ti_integracion` | Equipo TI Integración MT | `fx:manage`, `flags:manage`, `users:read`, `pricing:read`, imports |
| `gerente_comercial` | Gerente Comercial MT | `pricing:approve`, `pricing:reject`, recibe digest diario y escalaciones |

**Regla crítica (ADR-010):** Ningún precio puede integrarse a canales externos sin estar en estado `approved` o `auto_approved`. Esta regla se enforcea en BD (constraints) + runtime (FastAPI) + UI. **No tiene override por ningún rol.**

### 8.2 Cómo crear un usuario

1. Ir a `app.mtme.ae` → Menú → Administración → Usuarios
2. Click "Invitar usuario"
3. Ingresar email corporativo del usuario
4. Seleccionar rol: `ti_integracion` o `gerente_comercial`
5. Click "Enviar invitación"
6. El usuario recibe email con magic link (expira en 24h)

**Via API (requiere permiso `users:*`):**

```bash
curl -X POST https://app.mtme.ae/api/v1/users/invite \
  -H "Authorization: Bearer [JWT_ADMIN_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "nuevo.usuario@mt-middleeast.com",
    "role_code": "ti_integracion"
  }'
```

**Via Supabase Console (si la app no está disponible):**
1. Supabase Console → Authentication → Users → "Invite user"
2. Ingresar email → enviar
3. Luego asignar rol via SQL:
   ```sql
   UPDATE users
   SET role_id = (SELECT id FROM roles WHERE code = 'ti_integracion')
   WHERE email = 'nuevo.usuario@mt-middleeast.com';
   ```

### 8.3 Cómo desactivar un usuario

```bash
# Via API
curl -X PATCH https://app.mtme.ae/api/v1/users/[USER_UUID] \
  -H "Authorization: Bearer [JWT_ADMIN_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Via SQL (Supabase Console)
UPDATE users SET is_active = false WHERE email = 'usuario@mt-middleeast.com';

# Si es compromiso de seguridad → también desactivar en Supabase Auth:
-- Supabase Console → Auth → Users → buscar usuario → "Disable"
```

### 8.4 Cómo cambiar el rol de un usuario

```bash
# Via API
curl -X POST https://app.mtme.ae/api/v1/users/[USER_UUID]/role \
  -H "Authorization: Bearer [JWT_ADMIN_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"role_code": "gerente_comercial"}'

# Via SQL
UPDATE users
SET role_id = (SELECT id FROM roles WHERE code = 'gerente_comercial')
WHERE email = 'usuario@mt-middleeast.com';
```

### 8.5 Reset de contraseña y MFA

**Reset password (usuario bloqueado o forgot password):**
1. Supabase Console → Auth → Users → buscar email
2. Click "Send password reset email" o "Unlock" si está bloqueado

**Reset MFA (usuario perdió dispositivo):**

⚠️ Verificar identidad **fuera de banda** (videollamada + identificación) antes de hacer reset de MFA. Riesgo de phishing.

```bash
# Supabase Console → Auth → Users → usuario → "Disable MFA"
# Luego actualizar metadata para forzar re-enrolamiento:
UPDATE auth.users
SET raw_app_meta_data = raw_app_meta_data || '{"require_mfa_enrollment": true}'
WHERE email = 'usuario@mt-middleeast.com';
```

---

## 9. Jobs y scheduler

### 9.1 Lista de jobs programados

Los jobs están registrados en la tabla `job_definitions` (editable por TI sin redeploy) y ejecutados por Celery Beat con `DatabaseScheduler`.

| Job (task name) | Schedule | Queue | Propósito |
|-----------------|----------|-------|-----------|
| `mt.pricing.daily_digest` | Diario 14:00 UTC (18:00 UAE) | `pricing` | Resumen diario de precios para Gerente Comercial |
| `mt.pricing.parallel_run_diff` | Diario 04:00 UTC (08:00 UAE) | `pricing` | Compara precios app vs Excel referencia |
| `mt.pricing.escalate_pending` | Cada 2h | `pricing` | Escala precios en pending_review > 48h |
| `backup_postgres_daily` | Diario 02:00 GST | `audit` | Backup Postgres → R2 + B2 |
| `backup_storage_daily` | Diario 02:30 GST | `audit` | Backup Supabase Storage → R2 + B2 |
| `verify_backups_integrity` | Semanal domingos 04:00 GST | `audit` | Verifica que backups son restaurables |
| `mt.audit.partition_maintenance` | Semanal | `audit` | Crea particiones futuras `audit_events` |
| Heartbeat workers | Cada 15s (interno) | — | Publica heartbeat en Redis para healthcheck no-bloqueante |

### 9.2 Cómo verificar que los jobs corrieron

```bash
# Ver logs de un job específico en Better Stack Logs:
# Filtro: task_name:mt.pricing.daily_digest AND level:info
# Buscar lineas con "daily_digest: date=2026-05-12"

# Via SQL — ver historial de ejecuciones (si la app tiene tabla de job_runs):
SELECT
    task_name,
    started_at,
    finished_at,
    status,
    result
FROM job_runs
WHERE task_name = 'mt.pricing.daily_digest'
ORDER BY started_at DESC
LIMIT 10;

# Via Celery Flower (si está instalado en el entorno)
# http://localhost:5555 → Tasks → buscar por task name

# Via logs Beat
docker compose logs beat --tail=100 | grep "mt.pricing"
```

### 9.3 Qué hacer si un job no corrió

1. **Verificar que Beat está corriendo:**
   ```bash
   docker compose ps beat
   # Estado esperado: "healthy"
   
   docker compose logs beat --tail=50
   # Buscar: "Scheduler: Sending due task..."
   ```

2. **Si Beat está caído → restart:**
   ```bash
   docker compose restart beat
   ```

3. **Ejecutar job manualmente vía Celery:**
   ```bash
   # daily_digest
   docker compose exec worker celery -A app.workers.worker call \
     mt.pricing.daily_digest \
     --args='["2026-05-12"]'
   
   # parallel_run_diff
   docker compose exec worker celery -A app.workers.worker call \
     mt.pricing.parallel_run_diff \
     --args='["2026-05-12"]'
   
   # escalate_pending
   docker compose exec worker celery -A app.workers.worker call \
     mt.pricing.escalate_pending
   ```

4. **Si el job falla al ejecutar → ver logs Sentry:**
   - Sentry → Project `mt-api` → buscar issue con nombre del task

5. **Si el job requiere que Beat lo re-registre:**
   ```sql
   -- Verificar que el job existe en job_definitions
   SELECT code, enabled, cron_expression FROM job_definitions WHERE code LIKE 'mt.pricing%';
   
   -- Habilitar si está deshabilitado
   UPDATE job_definitions SET enabled = true WHERE code = 'mt.pricing.daily_digest';
   ```

---

## 10. Glosario

| Término | Definición |
|---------|-----------|
| **AED** | Dírham de los Emiratos Árabes Unidos. Moneda base de todos los precios en el sistema. |
| **ADR** | Architecture Decision Record — documento formal que registra una decisión arquitectónica y su justificación. |
| **Alembic** | Herramienta de migraciones de schema para SQLAlchemy/Postgres. Gestiona versiones del esquema de base de datos. |
| **Approval latency** | Tiempo transcurrido entre que un precio entra en `pending_review` y es aprobado/rechazado. SLO: p95 < 24h. |
| **auto_approved** | Estado de precio aprobado automáticamente porque el cambio de precio está dentro de la tolerancia configurada. No requiere intervención del Gerente. |
| **Beat** | Componente de Celery que funciona como scheduler (cron). Lee los jobs de `job_definitions` en BD y los encola en Redis. |
| **Better Stack** | Plataforma SaaS que cubre: logs centralizados, uptime monitoring, status page y on-call rotation. |
| **Canal** | Plataforma de venta donde se publica el precio: Amazon UAE FBA, Amazon UAE FBM, Noon, sitio direct B2C, etc. |
| **Celery** | Framework de cola de tareas distribuidas para Python. Los workers procesan tasks en background (imports, pricing, notificaciones). |
| **DatabaseScheduler** | Implementación custom de Celery Beat que lee el schedule de `job_definitions` en Postgres en lugar de un archivo estático. Permite editar jobs sin redeploy. |
| **Digest diario** | Email y notificación in-app que se envía al Gerente Comercial cada día a las 18:00 UAE con el resumen de precios del día. |
| **Docker Compose** | Herramienta para orquestar múltiples contenedores Docker. `docker-compose.dev.yml` para desarrollo local, `docker-compose.prod.yml` para producción. |
| **Doppler** | Gestor de secretos y variables de entorno. Centraliza todas las credenciales del proyecto. |
| **escalated** | Flag en un precio que indica que lleva > 48h en `pending_review` sin decisión del Gerente. El worker de escalación lo marca automáticamente. |
| **FBA** | Fulfillment by Amazon — esquema donde Amazon gestiona el almacenamiento y envío. Tiene estructura de costes diferente a FBM. |
| **FBM** | Fulfillment by Merchant — MT gestiona el almacenamiento y envío directamente. |
| **Feature flag** | Interruptor en BD que activa/desactiva una funcionalidad sin necesitar redeploy. Gestionado via `/admin/flags`. |
| **FX** | Foreign Exchange — tipo de cambio entre monedas. FX rate = el valor del cambio (ej. 1 USD = 3.6725 AED). |
| **FX swing** | Variación del tipo de cambio que puede justificar un recálculo masivo de precios. |
| **Gerente Comercial** | Rol en el sistema con permiso de aprobar/rechazar precios. En MT: Paula. |
| **GST** | Gulf Standard Time — zona horaria UAE (UTC+4). |
| **Healthcheck** | Endpoint que verifica el estado de salud de un componente del sistema. `/health/live` = evento loop responde; `/health/ready` = DB + Redis disponibles. |
| **Hetzner** | Proveedor de servidores cloud donde corre la aplicación de producción (Frankfurt o Helsinki para DR). |
| **Kill switch** | Mecanismo de emergencia que desactiva todos los features no críticos del sistema en un solo API call. |
| **MDM** | Master Data Management — gestión del maestro de datos (productos, costes, precios). |
| **Parallel run** | Período de operación dual donde el sistema nuevo y el Excel antiguo corren en paralelo para validar que los cálculos coinciden. |
| **pending_review** | Estado de un precio que requiere aprobación manual del Gerente Comercial porque el cambio de precio supera la tolerancia configurada. |
| **PIM** | Product Information Management — módulo que gestiona la información maestra de productos (specs, imágenes, traducciones). |
| **PITR** | Point-In-Time Recovery — capacidad de restaurar la base de datos a cualquier momento dentro de los últimos 7 días (Supabase). |
| **pricing engine** | Motor de cálculo de precios que aplica fórmulas, márgenes, costes, FX y reglas de excepción para calcular el precio de venta en cada canal. |
| **Queue** | Cola de mensajes en Redis donde Celery encola las tasks para que los workers las procesen. Queues: `imports`, `pricing`, `images`, `comparator`, `notifications`, `audit`, `default`. |
| **RLS** | Row Level Security — política de seguridad en Postgres que restringe qué filas puede ver cada rol de BD. |
| **rollback** | Revertir un deploy o migración a la versión anterior cuando algo falla. |
| **RPO** | Recovery Point Objective — cuánto tiempo de datos se puede perder en un desastre. Fase 1: 1 hora. |
| **RTO** | Recovery Time Objective — cuánto tiempo se puede tardar en restaurar el servicio. Fase 1: 4 horas. |
| **Runbook** | Documento paso a paso que describe cómo resolver un problema operativo específico. |
| **SEV1/SEV2/SEV3** | Niveles de severidad de incidentes: SEV1 = sistema caído, SEV2 = funcionalidad crítica degradada, SEV3 = bug menor. |
| **SKU** | Stock Keeping Unit — código único que identifica un producto específico. MT tiene ~224 SKUs activos. |
| **SLA** | Service Level Agreement — acuerdo de nivel de servicio. Para MT Fase 1: 99.5% disponibilidad en horario laboral GCC. |
| **SLI** | Service Level Indicator — métrica medible del servicio (ej. % requests exitosos). |
| **SLO** | Service Level Objective — objetivo numérico para un SLI (ej. disponibilidad > 99.5%). |
| **Supabase** | Backend-as-a-Service que provee Postgres, Auth, Storage y APIs. Toda la BD y Auth del proyecto. |
| **TI Integración** | Rol `ti_integracion` — equipo técnico de MT que gestiona importaciones, FX rates, feature flags y usuarios. |
| **UAT** | User Acceptance Testing — pruebas de aceptación de usuario. |
| **UAE PDPL** | UAE Personal Data Protection Law — ley de protección de datos de los Emiratos. Si hay breach de datos personales, notificar en 72h. |
| **Vector** | Agente de recolección y envío de logs (del stack Observabilidad). Lee logs Docker y los envía a Better Stack Logs. |
| **what-if / simulate** | Funcionalidad que permite calcular precios con parámetros hipotéticos sin guardar en BD. Endpoint: `POST /pricing/simulate`. |
| **Worker** | Proceso Celery que consume y ejecuta las tasks de una o varias queues. En producción puede haber múltiples workers por queue. |
