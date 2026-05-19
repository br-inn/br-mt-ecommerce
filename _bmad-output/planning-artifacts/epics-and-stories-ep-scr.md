---
stepsCompleted: [validate-prerequisites, design-epics, create-stories, final-validation]
inputDocuments:
  - docs/superpowers/plans/2026-05-16-brand-scraper.md
  - docs/superpowers/plans/2026-05-15-scraper-model-enriched-search.md
  - _bmad-output/implementation-artifacts/sprint-status.yaml
  - _bmad-output/planning-artifacts/adr/ADR-023-reverse-image-search-fallback.md
  - _bmad-output/planning-artifacts/adr/ADR-024-vlm-judge-audit-grade.md
  - _bmad-output/planning-artifacts/adr/ADR-025-capa-humana-permanente.md
  - _bmad-output/planning-artifacts/adr/ADR-026-hybrid-search-fase1.5.md
  - _bmad-output/planning-artifacts/adr/ADR-070-bright-data-scraping-policy.md
  - _bmad-output/planning-artifacts/adr/ADR-071-playwright-self-host-noon.md
  - _bmad-output/planning-artifacts/adr/ADR-072-amazon-sp-api-integration.md
  - _bmad-output/planning-artifacts/adr/ADR-073-vlm-judge-prompt-spec.md
generated: "2026-05-16T00:00:00.000Z"
project: "MT Middle East — Scraper, Matching & Comparador de Precios (EP-SCR consolidado)"
---

# EP-SCR — Scraper, Matching & Comparador de Precios

**Fuente:** Consolidación de EP-RND-01 (S7-S9) + EP-F15-02 (S10-S11) + EP-SCR-01 (S13 ad-hoc) + bugs detectados en verificación UI 2026-05-16  
**Stack:** FastAPI + SQLAlchemy 2.0 async + Celery + Redis | Next.js 16 + React 19 + Tailwind v4 + Shadcn new-york  
**ADRs que rigen este módulo:** ADR-023, ADR-024, ADR-025, ADR-026, ADR-070, ADR-071, ADR-072, ADR-073

---

## Requirements Inventory

### Functional Requirements

FR-01: Scraping por SKU individual (scrape_sku_task) y batch (scrape_batch_task) en Amazon UAE y Noon UAE con upsert en competitor_listings
FR-02: VLM Judge (claude-sonnet-4-6) evalúa candidatos con audit grade A/B/C/D y genera veredicto estructurado con reasoning y deal_breakers
FR-03: Reverse Image Search (CLIP) como capa de fallback cuando VLM confidence < 0.65, activable por feature flag
FR-04: Human Queue permanente — cola de revisión manual para grades C/D con flujo accept/reject/skip y captura de justificación
FR-05: Amazon SP API fetcher oficial con OAuth2 LWA, rate limiting 2 req/seg y token cache Redis
FR-06: Tradeling API adapter como fuente de precios B2B UAE
FR-07: Price Sanity Check P10/P90 pre-VLM para filtrar outliers de precio antes de evaluar candidatos
FR-08: Pool scrapeado (/comparator/pool) — vista de candidatos con filtros marketplace/estado, KPIs (Pendientes, Matched hoy, Agotadas, Últimos 7 días)
FR-09: Validación humana (/catalogo/validacion) — UI de revisión queue-based con navegación de candidatos, análisis de match y keyboard shortcuts
FR-10: Entidad CompetitorBrand con amazon_search_term, amazon_dept, amazon_category_node para scraping filtrado por marca
FR-11: API REST completa para competitor brands (POST/GET/PATCH) + endpoint POST /run para disparar scraping manual por brand_ids o todas las activas
FR-12: Frontend admin /admin/competitor-brands con tabla de marcas, dialogs create/edit y botón Run scraping
FR-13: Celery tasks scrape_brand_task y scrape_brands_batch_task — scraping por marca en Amazon UAE con upsert en competitor_listings con FK competitor_brand_id
FR-14: Test suite completo del módulo scraper — API CRUD + trigger, tasks con mock fetcher, Query builder unit tests (cobertura >= 80%)
FR-15: /comparator/pool — KPI cards y tabla resuelven a valores numéricos o 0; empty state cuando no hay resultados (nunca skeleton infinito)
FR-16: /admin/competitor-brands — todos los textos en español via i18n namespace admin.competitorBrands (ES/EN/AR)
FR-17: RBAC /admin/scraper — roles TI y Admin tienen acceso; Comercial ve read-only o no ve la sección según política definida
FR-18: Navegación lateral muestra "Marcas competidoras" para los roles autorizados en la sección Administración
FR-19: Job definition en tabla job_definitions para scraping diario automático de todas las marcas activas, configurable desde UI de Jobs Admin existente
FR-20: Dashboard de listings por marca /admin/competitor-brands/[id]/listings con tabla de candidatos scrapeados, filtros por precio/fecha/título y link al producto Amazon
FR-21: scrape_brand_task extendido a Noon UAE además de Amazon UAE, resultados en competitor_listings con source='noon_uae'
FR-22: Vista de comparación precios MT vs competidor — tabla que cruza competitor_listings (precio más bajo por SKU) con precios aprobados de MT
FR-23: price_daily_stats — vista materializada con agregados diarios P10/P90/avg/min/max de precio por listing; auto-refresh cada 24h; alimenta KPI dashboard y alertas
FR-24: Price alerts event-driven — detector de cambios de precio via trigger PostgreSQL en competitor_listings; umbral amarillo ≥5%, rojo ≥20%; campo resolved_at actualizado automáticamente cuando precio vuelve al rango normal; registro de quién acknowledgió y cuándo
FR-25: KPI dashboard de inteligencia de precios — vista /comparator/price-intelligence con Price Gap (%), Price Index (precio_MT / precio_promedio_mercado × 100) y Price Position (percentil) por SKU; filtros por categoría/marca/fecha
FR-26: Cross-encoder re-ranking — modelo de re-ranking (ms-marco-MiniLM o BGE-reranker) ordena los top-200 candidatos de pgvector a top-10 antes de pasar al VLM Judge; activable por feature flag cross_encoder_enabled; reduce costo de LLM sin perder recall
FR-27: HITL queue priorización por scoring — items en human queue ordenados por score = uncertainty × economic_value × is_first_appearance; uncertainty = 1 - confidence_score; economic_value configurable por categoría de producto; is_first_appearance = booleano para SKUs nunca vistos en la queue
FR-28: Circuit breaker por dominio en Redis — estado open/closed/half-open por dominio scrapeado; umbral: 5 fallos consecutivos = OPEN (300s); 1 request de prueba en HALF-OPEN antes de cerrar; estado visible en /admin/scraper dashboard
FR-29: TimescaleDB hypertable — migrar price_observations (o competitor_listings) a hypertable particionada por fetched_at; continuous aggregate price_daily_stats (FR-23) sobre hypertable; migración Alembic con rollback seguro; mejora 4× en queries de series temporales a 90 días
FR-30: Fingerprint rotation en scraper — rotar impersonación entre chrome120/chrome124/chrome126 en cada sesión nueva; configurable via SCRAPER_IMPERSONATE_POOL env var (lista separada por comas); evita fingerprint estático detectable
FR-31: Rate limiting ético y compliance técnico — token bucket por dominio en Redis (máx. 300 req/hora); delay base 10-30s configurable por dominio via settings; jitter ±50% aleatorio para evitar patrones fijos; robots.txt check cacheado 24h (no scrapetar paths en Disallow); sin CAPTCHA solving nunca (ScraperBlockedError y circuit breaker en cambio); backoff exponencial en reintentos: delay = base × 2^attempt + jitter; máx. 20 PDPs por sesión de IP antes de rotar proxy
FR-33: Gestión humana de bloqueos y observabilidad de canales — dashboard de salud por canal en /admin/scraper: % éxito rolling 7d, estado circuit breaker, requests/hora vs límite configurado; historial de incidentes (timestamp apertura, duración, causa: 403/CAPTCHA/timeout); alerta visible en dashboard + badge en nav si circuit breaker >48h abierto; suspensión manual de canal (pausa indefinida) + reactivación con request de prueba previa confirmación del operador

### NonFunctional Requirements

NFR-01: Test suite del módulo scraper con cobertura >= 80% en paths críticos (API routes, Celery tasks, Query builder)
NFR-02: Endpoints de competitor brands responden < 500ms bajo carga normal
NFR-03: Todos los textos nuevos de UI con i18n completo ES/EN/AR via namespaces de next-intl
NFR-04: Acceso a páginas admin usa RbacGuard con permisos del modelo RBAC existente del proyecto
NFR-05: Tasks de scraping usan rate limiter token bucket por dominio (Redis); backoff exponencial en reintentos; jitter ±50% en delays; nunca ráfagas fijas detectables
NFR-06: Jobs de scraping definidos en tabla job_definitions en DB, nunca hardcodeados en celery_config.py
NFR-07: Queries de series temporales en ventanas de 90 días responden <100ms con hypertable TimescaleDB + continuous aggregate (price_daily_stats)

### Additional Requirements

- Stack backend: FastAPI + SQLAlchemy 2.0 async + Alembic + Celery + Redis + Python 3.11
- Stack frontend: Next.js 16 + React 19 + TypeScript estricto + Tailwind v4 + Shadcn/ui new-york
- i18n: namespace admin.competitorBrands siguiendo patrón de admin.scraper existente
- RBAC: RbacGuard en Server Components, permisos products:read / scraper:read / scraper:write
- Jobs scheduling: tabla job_definitions + Celery Beat database scheduler (ADR-046)
- Tests: pytest + AsyncMock para tasks, AsyncClient para API routes, fixtures de DB en memoria
- Migraciones Alembic: naming convention YYYYMMDD_NNN_descripcion

### FR Coverage Map

FR-01: EP-SCR-01 — Scraping por SKU (scrape_sku_task + batch, adapters Amazon/Noon)
FR-02: EP-SCR-01 — VLM Judge (claude-sonnet-4-6, audit grades A/B/C/D)
FR-03: EP-SCR-01 — Reverse Image Search CLIP fallback con feature flag
FR-04: EP-SCR-01 — Human Queue permanente (accept/reject/skip + justificación)
FR-05: EP-SCR-01 — Amazon SP API fetcher (OAuth2 LWA, rate limit, Redis cache)
FR-06: EP-SCR-01 — Tradeling API adapter B2B
FR-07: EP-SCR-01 — Price Sanity Check P10/P90 pre-VLM
FR-08: EP-SCR-02 — Pool scrapeado UI (/comparator/pool) + fix skeleton (FR-15)
FR-09: EP-SCR-02 — Validación humana UI (/catalogo/validacion)
FR-10: EP-SCR-03 — CompetitorBrand entity (model + migration + schemas + repo)
FR-11: EP-SCR-03 — API REST competitor brands + /run trigger
FR-12: EP-SCR-03 — Frontend admin /admin/competitor-brands
FR-13: EP-SCR-03 — Celery scrape_brand_task + scrape_brands_batch_task
FR-14: EP-SCR-03 — Test suite completo (API + tasks + Query builder)
FR-15: EP-SCR-02 — Fix skeleton infinito en /comparator/pool
FR-16: EP-SCR-03 — i18n namespace admin.competitorBrands
FR-17: EP-SCR-03 — RBAC /admin/scraper roles TI/Admin/Comercial
FR-18: EP-SCR-03 — Navegación lateral "Marcas competidoras" para roles autorizados
FR-19: EP-SCR-04 — Job definition scraping diario automático
FR-20: EP-SCR-04 — Dashboard listings por marca /admin/competitor-brands/[id]/listings
FR-21: EP-SCR-04 — Noon UAE support en scrape_brand_task
FR-22: EP-SCR-04 — Vista comparación precios MT vs competidor
FR-23: EP-SCR-04 — price_daily_stats continuous aggregate P10/P90/avg/min/max diario por listing
FR-24: EP-SCR-04 — Price alerts event-driven (trigger PG, umbrales 5%/20%, resolved_at, acknowledgment)
FR-25: EP-SCR-04 — KPI dashboard /comparator/price-intelligence (Price Gap, Price Index, Price Position)
FR-26: EP-SCR-04 — Cross-encoder re-ranking Capa 2 matching pipeline (feature flag cross_encoder_enabled)
FR-27: EP-SCR-04 — HITL queue priorización scoring (uncertainty × economic_value × is_first_appearance)
FR-28: EP-SCR-03 — Circuit breaker por dominio Redis (open/closed/half-open, 5 fallos, 300s timeout)
FR-29: EP-SCR-04 — TimescaleDB hypertable price_observations + migración Alembic con rollback
FR-30: EP-SCR-03 — Fingerprint rotation (chrome120/124/126, SCRAPER_IMPERSONATE_POOL env var)
FR-31: EP-SCR-03 — Rate limiting ético por dominio (token bucket Redis, 300 req/hora, jitter, robots.txt, sin CAPTCHA)
FR-33: EP-SCR-03 — Gestión humana de bloqueos (dashboard salud, historial incidentes, pausa/reactivación manual)
FR-34: EP-SCR-04 — Heartbeat de scraping — last_successful_scrape_at por canal en Redis; alerta proactiva si >26h sin éxito; banner visible en /comparator/pool y /admin/scraper
FR-35: EP-SCR-04 — Monitor de calidad de matching — histograma de confidence scores 7d rolling en /admin/scraper; alerta si media baja >10pp respecto a baseline; % auto-aceptados vs cola humana por semana
FR-36: EP-SCR-03 — Proxy pool distribuido en Redis — lista circular RPOPLPUSH para rotación atómica entre workers; proxies fallidos con TTL cooldown 1h; integra con FR-38 (UI gestión proxies)
FR-37: EP-SCR-04 — Notificaciones externas de alertas de precio — email (SendGrid) para alertas red (gap ≥20%); Slack webhook opcional; configurable por rol (Gerente: red; TI: red+yellow); template con SKU/categoría/precios/gap%/link
FR-38: EP-SCR-03 — CRUD de proxies en UI — gestión del pool de proxies desde /admin/scraper con persistencia en DB y Redis; agregar/quitar/activar/desactivar sin redeploy; estado en tiempo real (activo/cooldown/fallido)
FR-39: EP-SCR-04 — Pipeline Bootstrap — UI sección "Bootstrap" en /admin/scraper con contador SKUs sin datos, filtro por categoría/marca, botón lanzar batch; feedback de progreso en tiempo real (chunks completados/total); re-bootstrap manual por SKU individual si match rechazado
FR-40: EP-SCR-04 — price_monitor_task liviana — fetch PDP directo (sin SERP ni VLM) para competitor_listings con match_status='accepted'; inserta en price_observations; evalúa delta vs precio anterior; flag out_of_stock=true si precio_aed=null; frecuencia configurable por categoría (default diario)
FR-41: EP-SCR-04 — UI diferenciación Bootstrap vs Monitoring — dos secciones en /admin/scraper: "Bootstrap" (SKUs sin datos, progreso) y "Price Monitoring" (SKUs en seguimiento, última actualización, próxima ejecución); métricas separadas; indicador cobertura X/Y SKUs activos con match validado
FR-42: EP-SCR-04 — Bootstrap Coordinator Task y colas dedicadas — bootstrap_coordinator_task parte SKUs en chunks vía celery.group despachados a bootstrap_queue; celery.chord para callback de finalización; deduplicación por SKU en Redis (SET NX TTL 1h); colas separadas: bootstrap_queue / monitoring_queue / vlm_queue
FR-43: EP-SCR-04 — Rate limiter centralizado en Redis — token bucket con Lua script atómico compartido entre TODOS los workers (no por worker); límite efectivo por dominio: 300 req/hora total; configurable via settings RATE_LIMIT_{DOMAIN}; workers esperan con backoff si sin tokens
FR-44: EP-SCR-04 — Worker containers especializados por cola — mt-worker-bootstrap (bootstrap_queue, concurrency=4, escalable), mt-worker-monitoring (monitoring_queue, concurrency=8), mt-worker-vlm (vlm_queue, concurrency=1); mt-beat siempre replicas=1
FR-45: EP-SCR-04 — Proxy pool distribuido en Redis con rotación atómica — RPOPLPUSH circular entre workers; cooldown de proxies fallidos (Redis TTL configurable); cada worker toma proxy al iniciar sesión sin colisiones; integra con FR-38
FR-46: EP-SCR-04 — Bootstrap worker on-demand multi-servidor — workers stateless conectables a Redis/DB del servidor principal solo con REDIS_URL+DATABASE_URL; script /infra/scripts/bootstrap-worker-start.sh con --autoscale=4,0 e idle timeout 5min; detención automática cuando queue vacía; progreso visible en UI (FR-41); compatibilidad Hetzner Private Network; opción futura BOOTSTRAP_AUTO_PROVISION via Hetzner Cloud API

## Epic List

### Epic EP-SCR-01: El sistema captura precios de competidores por SKU de forma automática
El equipo comercial y de TI dispone de un pipeline completo que scrapea Amazon UAE y Noon UAE para cada SKU del catálogo, evalúa candidatos con IA (VLM Judge + CLIP), filtra outliers de precio y enruta los casos de baja confianza a revisión humana.
**FRs cubiertos:** FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07
**Estado:** DONE (S7-S11, 44 SP entregados)
**Sprints:** S7 (human queue UI) · S8 (RIS hooks, shadow publish) · S9 (ComparatorService, POC G4) · S10 (SP API, VLM) · S11 (RIS on, Price Sanity, Tradeling)

### Epic EP-SCR-02: El equipo revisa y valida los resultados del comparador desde una interfaz centralizada
El equipo de TI y Comercial puede ver todos los candidatos scrapeados en el pool, filtrar por estado y marketplace, y el equipo de validación revisa la human queue con keyboard shortcuts, análisis de match y audit trail completo. La interfaz funciona sin estados skeleton infinitos.
**FRs cubiertos:** FR-08, FR-09, FR-15
**Estado:** PARCIAL — FR-08/09 done (S8-S11), FR-15 pendiente (bug skeleton pool)
**Sprints:** S8-S11 (pool + validación implementados) · S13 (fix skeleton)

---

## EP-SCR-02 — Historias

### Historia 2.1: Fix Empty State en Pool de Candidatos

Como miembro del equipo de TI o Comercial,
quiero que /comparator/pool muestre un estado vacío claro cuando no hay candidatos,
para poder saber inmediatamente que el pool está vacío y no confundirlo con un error de carga.

**Acceptance Criteria:**

**Given** que no hay registros en competitor_listings o los filtros activos no devuelven resultados
**When** el usuario visita /comparator/pool
**Then** los KPI cards muestran valores numéricos (0) en lugar de skeleton indefinido
**And** la tabla muestra empty state con icono y mensaje "No hay candidatos en el pool"
**And** el empty state incluye CTA "Lanzar scraping" que lleva a /admin/scraper

**Given** que hay candidatos pero el filtro activo no retorna resultados
**When** el usuario aplica el filtro
**Then** la tabla transiciona de datos a empty state sin pasar por skeleton
**And** el mensaje indica "No hay candidatos con estos filtros" con botón "Limpiar filtros"

**Given** que el componente está cargando datos reales (loading=true)
**When** la request está en vuelo
**Then** skeleton aparece máximo durante el tiempo de la request (timeout 10s)
**And** si la request falla, muestra error state con "Reintentar" — nunca skeleton infinito

**FRs cubiertos:** FR-15
**NFRs:** NFR-03 (i18n mensajes ES/EN/AR)
**Sprint:** S13

---

### Epic EP-SCR-03: El equipo gestiona las marcas competidoras con scraping resiliente y controlado
TI puede registrar marcas competidoras con sus parámetros de búsqueda en Amazon UAE, disparar scraping manual por marca o todas las activas, y ver los resultados en la tabla de admin. El módulo tiene test suite completo, textos en español, acceso controlado por roles, scraping resiliente con circuit breaker y rate limiting ético, y un dashboard de observabilidad para gestionar bloqueos manualmente.
**FRs cubiertos:** FR-10, FR-11, FR-12, FR-13, FR-14, FR-16, FR-17, FR-18, FR-28, FR-30, FR-31, FR-33, FR-36, FR-38
**Estado:** PARCIAL — FR-10/11/12/13 done (S13 ad-hoc), FR-14/16/17/18/28/30/31/33/36/38 pendientes
**Sprints:** S13 (implementación base) · S13/S14 (tests, RBAC, circuit breaker, rate limiter, proxy pool UI, fingerprint rotation)

---

## EP-SCR-03 — Historias

### Historia 3.1: i18n, RBAC y Navegación para Competitor Brands

Como miembro del equipo con rol TI o Admin,
quiero que /admin/competitor-brands tenga todos los textos en español, acceso controlado por rol y sea visible en la navegación lateral,
para que la sección sea consistente con el resto del sistema.

**Acceptance Criteria:**

**Given** que el namespace admin.competitorBrands no existe en los archivos de mensajes
**When** se agregan las keys a messages/es.json, messages/en.json, messages/ar.json
**Then** todos los textos de /admin/competitor-brands usan t('admin.competitorBrands.*') — cero strings hardcodeados
**And** título, columnas, labels de dialogs, botones y mensajes de error están traducidos en los 3 idiomas

**Given** un usuario con rol Comercial autenticado
**When** intenta acceder a /admin/competitor-brands
**Then** recibe 403 o es redirigido a /unauthorized
**And** la sección "Marcas competidoras" no aparece en su navegación lateral

**Given** un usuario con rol TI o Admin autenticado
**When** visita el layout de administración
**Then** ve "Marcas competidoras" en la sección Administración del sidebar con link activo correcto
**And** usuario Comercial en /admin/scraper ve read-only o acceso denegado según política de FR-17

**FRs cubiertos:** FR-16, FR-17, FR-18
**NFRs:** NFR-03, NFR-04
**Sprint:** S13

---

### Historia 3.2: Test Suite Completo del Módulo Competitor Brands

Como desarrollador del equipo,
quiero un test suite con cobertura ≥80% para el módulo competitor brands,
para poder refactorizar y extender el módulo con confianza y sin regresiones.

**Acceptance Criteria:**

**Given** que existen endpoints POST/GET/PATCH /competitor-brands y POST /competitor-brands/run
**When** se ejecuta pytest en el módulo scraper
**Then** los tests cubren: creación válida (201), validación campos requeridos (422), listado con paginación, update parcial, trigger /run con brand_ids específicos y con todas las activas
**And** cobertura ≥80% en api/routes/competitor_brands.py y repositories/competitor_brands.py

**Given** que existen tasks scrape_brand_task y scrape_brands_batch_task
**When** se ejecutan los tests con AsyncMock del fetcher
**Then** scrape_brand_task llama al fetcher con Query correcto (amazon_search_term, dept, category_node)
**And** resultados se upsertean en competitor_listings con competitor_brand_id correcto
**And** scrape_brands_batch_task despacha una task por cada brand activa

**Given** que Query tiene campos dept y category_node
**When** se ejecutan unit tests del Query builder
**Then** amazon_dept y amazon_category_node se mapean correctamente a Query.dept y Query.category_node
**And** la URL SERP contiene &i={dept} y &rh=n:{category_node} cuando están presentes

**Given** que se ejecuta pytest --cov
**When** el pipeline CI evalúa cobertura
**Then** falla si cobertura total del módulo baja de 80%

**FRs cubiertos:** FR-14
**NFRs:** NFR-01
**Sprint:** S13

---

### Historia 3.3: Rate Limiter Centralizado y Fingerprint Rotation

Como sistema de scraping con múltiples workers,
quiero un rate limiter compartido en Redis y rotación de fingerprints TLS,
para no superar 300 req/hora por dominio en total y evitar detección por fingerprint estático.

**Acceptance Criteria:**

**Given** que múltiples workers Celery corren simultáneamente
**When** cualquier adapter inicia una request HTTP
**Then** adquiere token del bucket Redis (rate_limit:{domain}:tokens) via Lua script atómico antes de la request
**And** total de requests a amazon.ae nunca supera 300/hora sin importar cuántos workers activos
**And** si no hay tokens, el worker espera con jitter ±50% — no falla inmediatamente

**Given** que SCRAPER_IMPERSONATE_POOL contiene ["chrome120","chrome124","chrome126"]
**When** el adapter inicia una nueva AsyncSession
**Then** selecciona aleatoriamente un fingerprint del pool en lugar del mismo siempre
**And** si SCRAPER_IMPERSONATE_POOL no está definido, usa SCRAPER_IMPERSONATE como fallback

**Given** que un test unitario del rate limiter corre con Redis de test
**When** se lanzan requests simultáneas que exceden el límite
**Then** solo las primeras N proceden; las demás esperan sin condición de carrera

**Given** que Redis no está disponible cuando el adapter intenta adquirir un token
**When** la conexión a Redis falla
**Then** el adapter procede con la request usando un delay fijo de seguridad (base_delay × 2) — nunca falla silenciosamente sin delay
**And** el error de conexión Redis se registra en logs como warning (no error crítico)

**FRs cubiertos:** FR-31, FR-30
**NFRs:** NFR-05
**Sprint:** S14

---

### Historia 3.4: Circuit Breaker por Dominio y Proxy Pool Distribuido

Como sistema de scraping,
quiero un circuit breaker por dominio en Redis y un proxy pool rotativo compartido,
para que un bloqueo de IP no paralice todos los workers y los proxies se distribuyan sin colisiones.

**Acceptance Criteria:**

**Given** que un dominio devuelve 5 ScraperBlockedError consecutivos
**When** ocurre el 5to error
**Then** el circuit breaker pasa a OPEN en Redis (TTL 300s)
**And** workers siguientes reciben CircuitOpenError sin hacer la request HTTP

**Given** que el circuit breaker está OPEN y pasan 300s
**When** un worker intenta una request
**Then** pasa a HALF_OPEN y permite exactamente 1 request de prueba
**And** éxito → CLOSED; fallo → OPEN con nuevo TTL; cambio registrado en historial

**Given** que SCRAPER_PROXY_POOL contiene proxies en Redis
**When** un worker inicia sesión
**Then** obtiene proxy via RPOPLPUSH atómico (sin colisiones entre workers)
**And** si el proxy tiene cooldown activo en Redis, rota al siguiente automáticamente
**And** si ningún proxy disponible, usa IP del servidor como fallback

**Given** que una request falla por error de conexión al proxy
**When** el adapter captura el error
**Then** marca el proxy en cooldown (Redis TTL 3600s) y reintenta con el siguiente proxy

**Given** que el circuit breaker transiciona de HALF_OPEN a CLOSED exitosamente
**When** la request de prueba tiene éxito
**Then** el dashboard en /admin/scraper actualiza el badge del canal a CLOSED=verde inmediatamente
**And** el historial registra: timestamp de cierre, duración total del incidente, modo de resolución (automático vs manual)

**FRs cubiertos:** FR-28, FR-36
**NFRs:** NFR-05
**Sprint:** S14

---

### Historia 3.5: Dashboard de Salud de Canales y Gestión de Proxies en UI

Como Rami (TI),
quiero ver el estado de salud de cada canal de scraping y gestionar proxies desde /admin/scraper sin redeploy,
para responder rápidamente a bloqueos y mantener el pool de proxies actualizado.

**Acceptance Criteria:**

**Given** que existen datos de scraping de los últimos 7 días
**When** Rami visita /admin/scraper
**Then** ve tabla de canales con: % éxito 7d rolling, estado circuit breaker (CLOSED=verde/OPEN=rojo/HALF_OPEN=amarillo), requests/hora vs límite, timestamp último scrape exitoso

**Given** que un canal tiene circuit breaker OPEN por más de 48 horas
**When** cualquier usuario TI o Admin visita /admin/scraper o /comparator/pool
**Then** aparece banner de alerta con nombre del canal y horas bloqueado
**And** badge rojo en la navegación lateral

**Given** que Rami necesita pausar un canal manualmente
**When** hace click en "Pausar canal" y confirma
**Then** circuit breaker se fuerza a OPEN indefinido (sin TTL automático)
**And** botón cambia a "Reactivar" con indicador "Pausa manual activa"

**Given** que Rami hace click en "Reactivar" un canal pausado
**When** confirma la reactivación
**Then** el sistema lanza 1 request de prueba y muestra el resultado antes de reanudar
**And** si la prueba falla, el canal vuelve a OPEN normal con TTL automático

**Given** que Rami necesita gestionar proxies
**When** usa el formulario de proxies en /admin/scraper
**Then** puede agregar URL de proxy, activar/desactivar existentes, ver estado (activo/cooldown/fallido)
**And** cambios persisten en DB y sincronizan a Redis inmediatamente sin redeploy

**FRs cubiertos:** FR-33, FR-38
**NFRs:** NFR-02, NFR-03, NFR-04
**Sprint:** S14

---

### Epic EP-SCR-04: El sistema ejecuta monitoreo autónomo y genera inteligencia de precios accionable
TI configura el scraping de marcas para ejecutarse automáticamente cada día con TimescaleDB para histórico eficiente. Comercial y Gerente acceden a un dashboard de price intelligence con Price Gap, Price Index y Price Position por SKU, reciben alertas automáticas de cambios de precio significativos, y el pipeline de matching mejora su precisión con cross-encoder re-ranking y priorización inteligente de la cola humana. La cobertura se extiende a Noon UAE.
**FRs cubiertos:** FR-19, FR-20, FR-21, FR-22, FR-23, FR-24, FR-25, FR-26, FR-27, FR-29, FR-34, FR-35, FR-37, FR-39, FR-40, FR-41, FR-42, FR-43, FR-44, FR-45, FR-46
**Estado:** PENDIENTE (S14-S16)
**Sprints:** S14 (job scheduling + listings + Noon + TimescaleDB + Bootstrap coordinator + colas + rate limiter centralizado) · S15 (price alerts + KPI dashboard + notificaciones externas + heartbeat + monitor calidad) · S16 (cross-encoder + HITL scoring + on-demand workers + auto-provisioning)

---

## EP-SCR-04 — Historias

### Historia 4.1: TimescaleDB Hypertable para Histórico de Precios

Como sistema de price intelligence,
quiero que el histórico de precios use una hypertable TimescaleDB con agregados diarios materializados,
para que las queries de series temporales respondan en <100ms a 90 días de datos sin degradar con el volumen.

**Acceptance Criteria:**

**Given** que TimescaleDB está disponible como extensión en el contenedor PostgreSQL
**When** se ejecuta la migración Alembic (YYYYMMDD_NNN_timescaledb_hypertable)
**Then** price_observations se convierte en hypertable particionada por observed_at
**And** la migración incluye rollback probado que revierte sin pérdida de datos
**And** la migración es ejecutable con la tabla activa (rename + backfill, no DROP/CREATE)

**Given** que price_observations es hypertable
**When** se crea la vista materializada price_daily_stats
**Then** contiene por (listing_id, día): min, max, avg, P10, P90 de price_aed
**And** se refresca automáticamente cada 24h via add_continuous_aggregate_policy
**And** query de 90 días responde <100ms en dataset de prueba con 1M rows

**Given** que SQLAlchemy hace queries a price_observations
**When** se ejecutan queries existentes sin cambios
**Then** funcionan correctamente — TimescaleDB es transparente para el ORM
**And** tests de integración existentes pasan sin modificación

**Given** que el contenedor PostgreSQL no tiene la extensión TimescaleDB instalada
**When** el backend inicia y ejecuta el check de extensiones en lifespan startup
**Then** el startup falla con error explícito: "TimescaleDB extension not available — run: CREATE EXTENSION timescaledb"
**And** el error incluye instrucciones de instalación — nunca falla silenciosamente degradando a Postgres puro

**FRs cubiertos:** FR-29, FR-23
**NFRs:** NFR-07
**Sprint:** S14

---

### Historia 4.2: price_monitor_task y Workers Especializados por Cola

Como sistema de scraping,
quiero una task liviana de monitoreo de precios y workers especializados por tipo de trabajo,
para actualizar precios de matches validados eficientemente sin ejecutar el pipeline completo de matching.

**Acceptance Criteria:**

**Given** que existe un competitor_listing con match_status='accepted' y ASIN conocido
**When** price_monitor_task(listing_id, asin, source) se ejecuta
**Then** hace fetch del PDP directo (sin SERP) usando el ASIN del match validado
**And** extrae price_aed actual e inserta en price_observations con observed_at=now()
**And** si producto no disponible, inserta con price_aed=null y out_of_stock=true
**And** NO invoca VLM Judge ni HITL — solo fetch de precio

**Given** que la configuración define colas bootstrap_queue, monitoring_queue, vlm_queue
**When** se despliega el docker-compose.dev.yml actualizado
**Then** mt-worker-monitoring consume monitoring_queue con concurrency=8
**And** mt-worker-vlm consume vlm_queue con concurrency=1
**And** mt-worker-bootstrap consume bootstrap_queue con concurrency=4 y --autoscale=4,0
**And** mt-beat tiene replicas: 1 — nunca escalar

**Given** que price_monitor_batch_task se ejecuta
**When** orquesta el monitoring de todos los matches aceptados
**Then** despacha una price_monitor_task por cada listing a monitoring_queue respetando rate limiter Redis

**Given** que el ASIN de un match validado devuelve HTTP 404 (producto eliminado de Amazon)
**When** price_monitor_task recibe el 404
**Then** actualiza competitor_listing con match_status='unavailable' y fetched_at=now()
**And** inserta en price_observations con price_aed=null y out_of_stock=true
**And** NO dispara price_alert — la indisponibilidad no es un cambio de precio

**FRs cubiertos:** FR-40, FR-43, FR-44, FR-45
**NFRs:** NFR-05, NFR-06
**Sprint:** S14

---

### Historia 4.3: Bootstrap Coordinator y Workers On-Demand

Como Rami (TI),
quiero poder lanzar el bootstrap de scraping para SKUs sin datos desde la UI,
con soporte para workers adicionales en servidores externos que se conectan automáticamente sin redeploy,
para escalar el bootstrap horizontalmente cuando el catálogo crece.

**Acceptance Criteria:**

**Given** que existen SKUs sin competitor_listings con match_status='accepted'
**When** bootstrap_coordinator_task se ejecuta
**Then** parte SKUs en chunks de 50 (configurable), despacha scrape_chunk_task a bootstrap_queue via celery.group
**And** usa celery.chord para callback de finalización cuando todos los chunks completan
**And** deduplicación via Redis SET NX TTL=3600s — SKUs in_progress no se reencolan

**Given** que scrape_chunk_task procesa candidatos de un SKU listos para evaluación VLM
**When** los candidatos superan el Price Sanity Check y el cross-encoder los re-rankea
**Then** encola vlm_eval_task en vlm_queue — NO invoca VLM directamente desde el worker bootstrap
**And** el worker bootstrap espera el resultado via Celery result backend antes de continuar con el siguiente SKU del chunk
**And** con 10 workers bootstrap activos, el sistema hace exactamente 1 llamada VLM a la vez (concurrency=1 de mt-worker-vlm)

**Given** que un worker bootstrap externo tiene solo REDIS_URL y DATABASE_URL configurados
**When** ejecuta docker run mt-backend celery -Q bootstrap_queue --autoscale=4,0
**Then** se conecta a Redis y procesa la queue automáticamente sin configuración adicional
**And** cuando la queue está vacía por 5 minutos, el worker se detiene solo

**Given** que todos los chunks del bootstrap_coordinator completan (chord callback)
**When** el último scrape_chunk_task termina
**Then** el coordinator actualiza Redis: bootstrap:status=completed, bootstrap:completed_at=now()
**And** el dashboard de /admin/scraper muestra "Bootstrap completado: X SKUs procesados, Y aceptados automáticamente, Z en cola HITL"
**And** si FR-37 está activo, envía email de finalización a TI con el resumen

**Given** que el bootstrap está en ejecución
**When** Rami visita la sección "Bootstrap" en /admin/scraper
**Then** ve: SKUs en queue, chunks completados/total, workers activos conectados a Redis
**And** puede hacer re-bootstrap manual de un SKU individual si su match fue rechazado

**Given** que /admin/scraper tiene las dos secciones
**When** Rami navega entre "Bootstrap" y "Price Monitoring"
**Then** "Bootstrap" muestra SKUs sin datos con filtro por categoría/marca y botón "Lanzar Bootstrap"
**And** "Price Monitoring" muestra total monitoreados, última actualización por canal, próxima ejecución, cobertura X/Y SKUs

**FRs cubiertos:** FR-42, FR-46, FR-39, FR-41
**NFRs:** NFR-05
**Sprint:** S14

---

### Historia 4.4: Job Definitions para Scraping Automático Diario

Como Rami (TI),
quiero que el scraping de marcas se ejecute automáticamente cada día según jobs configurables en la UI,
para no tener que lanzar manualmente el scraping cada día.

**Acceptance Criteria:**

**Given** que la tabla job_definitions y la UI de Jobs Admin existen
**When** se agregan las definiciones de jobs de scraping
**Then** existe scraping_brands_monitoring — ejecuta price_monitor_batch_task diario a las 03:00 UTC (configurable)
**And** existe scraping_brands_bootstrap — ejecuta bootstrap_coordinator_task para marcas nuevas sin datos

**Given** que scraping_brands_monitoring está activo
**When** Celery Beat ejecuta el job a la hora programada
**Then** price_monitor_batch_task se encola en monitoring_queue respetando rate limiter

**Given** que una brand tiene noon_search_term configurado
**When** scrape_brand_task se ejecuta para esa brand
**Then** lanza fetch en noon.ae con el término de búsqueda
**And** resultados se upsertean en competitor_listings con source='noon_uae' y competitor_brand_id correcto

**Given** que Rami edita la frecuencia del job desde la UI de Jobs Admin
**When** guarda el cambio
**Then** Celery Beat aplica el nuevo schedule sin redeploy

**Given** que price_monitor_batch_task del ciclo anterior aún está corriendo
**When** Celery Beat dispara el siguiente ciclo programado
**Then** el nuevo trigger detecta la task activa via Redis lock (SET NX) y no lanza un segundo run simultáneo
**And** registra en logs: "price_monitor_batch skipped — previous run still active (started {timestamp})"
**And** si el run anterior lleva más de 2× el tiempo esperado, genera alerta de heartbeat (FR-34)

**FRs cubiertos:** FR-19, FR-21
**NFRs:** NFR-06
**Sprint:** S14

---

### Historia 4.5: Price Alerts Event-Driven con Heartbeat y Notificaciones Externas

Como Yasmin (Gerente Comercial),
quiero recibir alertas automáticas por email cuando el precio de un competidor cambia significativamente,
para poder reaccionar el mismo día sin necesitar entrar al sistema.

**Acceptance Criteria:**

**Given** que existe trigger PostgreSQL en competitor_listings.price_aed
**When** price_monitor_task actualiza price_aed
**Then** el trigger calcula delta y dispara pg_notify('price_change', payload_json) si abs(delta) >= 5%
**And** el listener asyncio encola evaluate_price_alert_task en Celery

**Given** que evaluate_price_alert_task recibe el payload
**When** delta >= 5% y < 20%
**Then** crea registro en price_alerts con severity='yellow', delta_pct, triggered_at, resolved_at=null
**And** cuando delta >= 20%, crea alerta con severity='red'
**And** cuando precio vuelve a rango normal (<5%), actualiza resolved_at=now() automáticamente

**Given** que existe una alerta red activa
**When** se crea el registro en price_alerts
**Then** se envía email via SendGrid a usuarios Gerente Comercial con notificaciones red activadas
**And** el email contiene: SKU, categoría, precio MT, precio competidor, gap%, link a /comparator/price-intelligence
**And** usuarios TI con notificaciones reciben email para alertas red y yellow

**Given** que last_successful_scrape_at por canal se almacena en Redis
**When** han pasado más de 26h sin scrape exitoso
**Then** aparece banner en /comparator/pool y /admin/scraper: "Canal [nombre] sin actualización desde [N]h"
**And** si TI tiene notificaciones activadas, se envía email de heartbeat failure

**FRs cubiertos:** FR-24, FR-34, FR-37
**NFRs:** NFR-07
**Sprint:** S15

---

### Historia 4.6: KPI Dashboard de Price Intelligence y Vista Comparación

Como Ana (Comercial) y Yasmin (Gerente),
quiero ver el Price Gap, Price Index y Price Position agrupados por categoría con drill-down a SKU,
para identificar rápidamente dónde estamos más caros o baratos que el mercado.

**Acceptance Criteria:**

**Given** que existen datos en price_daily_stats
**When** Ana visita /comparator/price-intelligence
**Then** ve vista principal agrupada por categoría con semáforo: verde (<5%), amarillo (5-20%), rojo (>20%)
**And** cada categoría muestra: Price Index promedio, Price Position (percentil), conteo SKUs por color

**Given** que Ana hace click en una categoría en rojo
**When** se expande el drill-down
**Then** ve tabla de SKUs con: nombre, precio MT, precio competidor más bajo, Price Gap (%), Price Position, fecha dato

**Given** que el usuario aplica filtros por marca o fecha
**When** los filtros se aplican
**Then** KPIs se recalculan en <500ms y los filtros persisten en URL (shareable links)

**Given** que el usuario visita /admin/competitor-brands/[id]/listings
**When** la página carga
**Then** ve tabla con: título, precio AED, fuente, fecha scrape con frescura (verde <24h, amarillo 1-7d, rojo >7d), precio MT si existe match aceptado
**And** columna "Efectividad" = candidatos_encontrados / scrapes_ejecutados_últimos_30d × 100% — denominador son los scrapes de los últimos 30 días para esa brand, no el total histórico

**FRs cubiertos:** FR-25, FR-22, FR-20
**NFRs:** NFR-02, NFR-03
**Sprint:** S15

---

### Historia 4.7: Monitor de Calidad de Matching

Como Rami (TI),
quiero ver la distribución de confidence scores del pipeline de matching y recibir alerta si la calidad degrada,
para detectar cuando el modelo pierde precisión por cambios en el formato de productos.

**Acceptance Criteria:**

**Given** que existen confidence_scores de los últimos 7 días
**When** Rami visita la sección de calidad en /admin/scraper
**Then** ve histograma de distribución por rango: <0.60, 0.60-0.85, >0.85
**And** métricas semanales: % auto-aceptados, % cola humana, % rechazados

**Given** que el baseline de confidence media está establecido
**When** la media actual baja más de 10pp respecto al baseline
**Then** aparece alerta en dashboard: "Calidad de matching degradada — actual X% vs baseline Y%"
**And** TI recibe email de alerta si notificaciones activadas

**Given** que Rami quiere actualizar el baseline
**When** hace click en "Establecer como baseline"
**Then** la semana actual se marca como nueva referencia con timestamp y usuario registrado

**FRs cubiertos:** FR-35
**NFRs:** NFR-02
**Sprint:** S15

---

### Historia 4.8a: Cross-Encoder Re-ranking con Cache y Prompt Caching

Como sistema de matching,
quiero re-rankear candidatos con un cross-encoder antes del VLM y activar Anthropic prompt caching,
para reducir el costo de LLM en ~50% sin pérdida de calidad de matching.

**Acceptance Criteria:**

**Given** que el feature flag cross_encoder_enabled está activo
**When** el pipeline obtiene top-200 candidatos de pgvector
**Then** el cross-encoder (ms-marco-MiniLM-L-6-v2) re-rankea y retorna top-10
**And** solo esos top-10 pasan al VLM Judge — reduciendo llamadas a Anthropic ~95%
**And** si el flag está desactivado, comportamiento idéntico al actual (top-10 directo de pgvector)

**Given** que el cross-encoder está configurado
**When** el backend inicia en lifespan startup
**Then** el modelo se descarga y carga en memoria una vez (warmup <10s)
**And** latencia de re-ranking <20ms por query en CPU del worker
**And** si el modelo no está disponible, el startup falla con error explícito — nunca silencioso

**Given** que un par (query_content_hash, asin) ya fue evaluado por VLM en las últimas 24h
**When** el mismo par aparece en otro bootstrap
**Then** reutiliza el veredicto cacheado en Redis (vlm_verdict:{query_hash}:{asin}) sin invocar VLM
**And** el cache hit se registra como métrica cache_hit_rate visible en monitor de calidad (FR-35)
**And** el TTL es configurable (default 24h via SCRAPER_VLM_CACHE_TTL)

**Given** que el sistema construye el mensaje para Anthropic API
**When** se envía el system prompt del VLM Judge
**Then** el system prompt incluye cache_control: {"type": "ephemeral"} para activar Anthropic prompt caching
**And** el ahorro de prompt caching se registra como métrica vlm_prompt_cache_savings en logs

**FRs cubiertos:** FR-26
**NFRs:** NFR-05
**Sprint:** S16
**Prerequisito:** 4.2 (vlm_queue especializada)

---

### Historia 4.8b: HITL Queue con Priorización y Threshold de Alto Valor

Como reviewer humano en /catalogo/validacion,
quiero que la cola de revisión esté ordenada por impacto económico e incertidumbre,
y que los SKUs de alto valor sean revisados aunque la IA los haya aceptado,
para asegurar calidad en los matches más importantes para el negocio.

**Acceptance Criteria:**

**Given** que un item entra a la human queue (confidence 0.60-0.85)
**When** se calcula su posición en la cola
**Then** score = (1 - confidence_score) × economic_value × is_first_appearance_multiplier
**And** economic_value = price_daily_stats.price_avg del SKU en los últimos 7 días (proxy de valor de mercado) — si no hay datos, usa competitor_listing.price_aed
**And** is_first_appearance_multiplier = 2.0 si el SKU nunca tuvo match revisado, 1.0 si ya tuvo
**And** /catalogo/validacion muestra items ordenados por score descendente (mayor prioridad primero)
**And** la UI muestra para cada item: confidence score, precio del SKU, indicador "Primera vez" si aplica

**Given** que un SKU tiene price_daily_stats.price_avg mayor al umbral (default AED 1.000, configurable via HIGH_VALUE_SKU_THRESHOLD_AED)
**When** el VLM Judge retorna grade A o B (auto-accept normal)
**Then** el sistema igualmente encola el match en HITL queue con flag high_value_review=true
**And** en /catalogo/validacion aparece con badge "Alto valor — revisar aunque IA aceptó"
**And** el threshold es configurable sin redeploy

**Given** que el reviewer aprueba o rechaza un item high_value_review
**When** completa la revisión
**Then** el flag high_value_review queda registrado en competitor_listing.audit_metadata
**And** el match_status se actualiza según la decisión del reviewer (no el grade VLM original)

**FRs cubiertos:** FR-27
**NFRs:** NFR-05
**Sprint:** S16
**Prerequisito:** 4.1 (price_daily_stats para economic_value), 4.8a (vlm_queue y pipeline)

