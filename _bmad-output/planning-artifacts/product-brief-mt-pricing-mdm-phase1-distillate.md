---
title: "Product Brief Distillate: MT Middle East — Plataforma de Datos Maestros y Pricing (Fase 1)"
type: llm-distillate
source: "product-brief-mt-pricing-mdm-phase1.md"
version: "1.3"
created: "2026-05-06"
updated: "2026-05-06"
purpose: "Token-efficient context for downstream PRD creation"
project_name: "mt-pricing-mdm-phase1"
client_relationship: "BR Innovation → MT Middle East (single-tenant build custom)"
changelog:
  - "1.0 (2026-05-06): versión inicial."
  - "1.2 (2026-05-06): Pivot a FastAPI + Supabase + Hetzner alineado con `hppt-iom`. Sources reales descubiertas integradas. ADRs 028-037 nuevas; ADR-001/005/013/018/021 superseded total/parcialmente."
  - "1.3 (2026-05-06): integra ADR-045 (persistencia híbrida SQLAlchemy 2.0 async + supabase-py Auth/Storage) y ADR-046 (Celery Beat con DatabaseScheduler editable). Stack propuesto y decisiones tomadas actualizados."
---

# Detail Pack — MT Middle East Master Data + Pricing (Fase 1)

## Contexto del programa
- **Cliente final**: MT Middle East (mtme.ae, Dubái) — unidad GCC de MT Valves España (Pallejà, ESP). Dominio hidrosanitario / válvulas industriales.
- **Desarrollador**: BR Innovation (psierra@br-innovation.com — operador). Sponsor MT: Christian. Validador técnico MT: Paula.
- **Modelo comercial**: BR como vendor / MT como cliente. **Single-tenant**, sin white-label ni multi-cliente.
- **Programa multi-fase** (4 fases):
  - Fase 1 (este brief): Master Data + Pricing — uso interno MT.
  - Fase 2: Inventarios, facturación, costos operativos.
  - Fase 3: Storefront B2C UAE + marketplaces (Amazon UAE, Noon UAE) en vivo.
  - Fase 4: Portal B2B distribuidores GCC.
- **Stack del master doc descartado** (Shopify+Supabase+Make.com): se redefine.

## Roles / RBAC Fase 1
| Rol | Capacidades clave |
|-----|-------------------|
| Comercial Canal Online & Marketplaces | CRUD catálogo, alta SKU, propuesta de precios por canal/esquema, traducciones, disparo de imports |
| Gerente Comercial | Aprueba excepciones (cambios > X% margen, alertas críticas), revisa digest diario, define reglas paramétricas de excepción |
| TI de Integración | Configura connectors futuros, monitorea sincronización, gestiona usuarios/permisos. Definir si FTE / role-share / vendor en S0 |
| Backup operator (cross-trained) | Mitiga single-point-of-failure del Comercial — requerido antes del cutover |
| Champion del cambio | Persona del equipo Comercial con ≥30 % dedicación durante migración |

## Modelo de datos núcleo
- `products` — sku, name_en (canónico), name_es, name_ar, family, dn, pn, type, material, specs JSONB, image_url, translation_status (per language: pending/draft/approved), data_quality (complete/partial/blocked), active, audit fields.
- `suppliers` — nombre, condiciones, moneda contractual, lead time, contacto, activo.
- `costs` — sku × scheme × supplier, breakdown desglosado (FOB, freight, customs, FBA fees, FBM fees, payment fees, marketing), moneda origen, FX as-of, audit.
- `prices` — sku × channel × scheme, price (en moneda canal), pvp_min, margin %, rule_applied, breakdown, alerts (critical/warning), valid_from / valid_to, status (draft/auto_approved/pending_review/approved/rejected/revised/exported), proposed_by, approved_by, FX as-of, audit.
- `channels` — code, name, state (`inactive` / `pre_launch` / `pilot` / `live` / `paused` / `deprecated`), schemes_supported (FBA, FBM, Direct B2C, Direct B2B, Marketplace), state_history.
- `schemes` — code, name (FBA, FBM, Direct B2C, Direct B2B, Marketplace), cost_components_template, channel_compatibility.
- `currencies` — base configurable (default AED). Tabla `fx_rates` versionada (from→to, rate, effective_from, effective_to, source).
- `exception_rules` — paramétricas: threshold de margen %, FX swing %, regla por canal, regla por esquema.
- `audit_events` — todas las tablas críticas; triggers Postgres.
- `embedding VECTOR(1536)` reservado en `products` y `competitor_listings` para Fase 1.5+ (no se llena en Fase 1).

## Workflow de aprobación por excepción
- **Cambios dentro de tolerancia** (≤ X% margen, X parametrizable, default 5-10 %): `auto_approved` automático.
- **Cambios fuera de tolerancia / críticos**: `pending_review` → firma del Gerente Comercial.
- Triggers de excepción: variación de margen > X%, cambio de regla aplicada, FX swing > Y%, alerta crítica de pricing, margen < mínimo, costos cambian > Z%.
- **Bulk review**: Gerente recibe digest diario (auto_approved del día + pendientes).
- **Regla dura no-negociable**: ningún registro sale por integración/connector si su estado ≠ `approved` ni `auto_approved`. Enforcement a nivel modelo (DB constraint) + runtime (connector filtra y rechaza).
- State machine: `draft → auto_approved | pending_review → approved | rejected | revised → exported`.

## Sistema de comparación de productos (research workstream — punto crítico)
- **Hoy v5.1 falla en 15 % del catálogo** (34/224 sin match + 34 NONE tier). No es port, es rediseño con investigación.
- **Preguntas abiertas** a responder en S0-S6 con evidencia:
  - Estrategia de búsqueda: cómo se generan candidatos por SKU (queries Amazon UAE / Noon / supplier sites; uso de specs vs nombre comercial; multi-idioma EN/AR).
  - Sourcing de datos competitivos: scraping vs API oficial vs datasets pagos (Keepa, DataForSEO, RapidAPI) vs partnerships marketplace. Costo, sostenibilidad, legalidad UAE.
  - LLM de comparación de imágenes: GPT-4o vision / Claude vision / Gemini / CLIP / SigLIP / open-CLIP / Pinecone Image / AWS Rekognition. Benchmark con dataset etiquetado ≥ 50 pares true-match/true-mismatch + tabla coste-vs-accuracy.
  - Comparación de datos técnicos: reglas duras (DN, PN, material, tipo, conexión) + similitud semántica de texto. Pesos justificados + tabla de "deal breakers" (DN distinto = no-match aunque imagen coincida).
  - Calibración de confianza: Platt / isotonic / conformal prediction. Curva de calibración + threshold operativo.
  - Validación humana asistida: UI de "validación rápida" + estimación de carga semanal sin convertirse en cuello de botella.
- **Hipótesis a validar (no decisiones)**:
  - Embeddings imagen + embeddings texto técnico + reglas duras > cualquier dimensión sola.
  - Modelos visión generales no rinden bien en hardware industrial sin fine-tuning ni specs estructuradas como contexto.
  - pgvector + HNSW alcanza con < 1M filas; decisión de embeddings independiente del stack.
- **Métricas objetivo**: false-positive < 2 %, false-negative < 10 %, calibración (cuando dice 85 % es 85 % real), cobertura ≥ 90 % de SKUs con candidato auditado.
- **Dataset de calibración**: real, etiquetado por humano, no los datos demo del Excel.
- **Si no llega**: se difiere a Fase 1.5 sin bloquear el resto de Fase 1.

## Carga inicial del catálogo
- **Excel `stock_dubai_v23` = datos demo** + especificación de modelo de datos + fixture de pruebas. NO es source operativa.
- **Sources reales confirmadas**: archivo PIM + archivos de costos de productos (a recibir en Sprint 0).
- **Estrategia**:
  - Importer dedicado para PIM (artículos + specs + idiomas + imágenes).
  - Importer separado para costos (líneas desglosadas SKU × esquema).
  - Validación cruzada: SKUs de costos sin PIM = huérfanos reportables.
  - FX as-of stamping por batch.
- **Excel demo**: post-carga del PIM real, queda archivado read-only (`_ARCHIVE_YYYY-MM-DD`).

## Sistema de monedas
- **Moneda base** configurable. Default sugerido: **AED** (operación UAE).
- **Tabla `fx_rates` versionada** (from, to, rate, effective_from, effective_to, source).
- Cada precio y coste **guarda el FX vigente** al momento de aprobación (no se recalcula al pasado).
- Importer estampa **FX as-of por batch**; precios pre-existentes marcan `migrated, FX inferred`.
- TC actual demo: 1 EUR = 4,29 AED (abril/mayo 2026, hardcoded VBA en Excel).

## i18n
- **UI**: ES + EN (selector usuario interno).
- **Datos canónicos**: EN (NOT NULL).
- **Traducciones**: ES + AR (nullable, con `translation_status` por SKU/idioma: pending/draft/approved).
- **Sin RTL UI** en Fase 1 (AR es sólo contenido para export externo).
- Recomendado: react-i18next o next-intl si stack JS.

## Stack propuesto (sujeto a firma TI MT en S0) — pivot 2026-05-06 alineado con `hppt-iom`
- **Frontend**: Next.js 16 (App Router) + React 19 + **React Compiler** + TypeScript estricto + Tailwind v4 + Shadcn/ui (new-york) + Radix + Lucide + Zod + next-intl.
- **Backend API**: **FastAPI 0.x** sobre **Python 3.11** + Pydantic v2 + Pydantic Settings + APScheduler (schedules ligeros) + Gunicorn + Uvicorn workers.
- **Worker async**: **Celery** (broker Redis) — imports masivos, recálculos, OCR, embeddings, fan-out comparador.
- **DB**: **Supabase Postgres** con **RLS + pgvector + uuidv7 + particionado**. Migrations split: Alembic gestiona `public.*` (tablas aplicativas), Supabase migrations gestiona `auth.*`/`storage.*`/RLS críticas (ADR-045 §8.0.4).
- **Capa de acceso a datos (ADR-045)**: persistencia **híbrida** — **SQLAlchemy 2.0 async + Alembic** para core data (products, prices, costs, audit_events, job_definitions, comparator) + **supabase-py** SOLO para Auth/Storage/admin. Backend usa dos clientes coordinados (`app/core/db.py` + `app/core/supabase.py`). App conecta con rol Postgres `mt_app` que respeta RLS.
- **Auth/RBAC**: **Supabase Auth** (JWT verificado en backend FastAPI + RLS policies por rol en BD). Force-logout en revocación de rol via `supabase.auth.admin.sign_out(user_id)`.
- **Scheduler (ADR-046)**: **Celery Beat con DatabaseScheduler editable** — schedules en tabla `job_definitions` (Postgres), UI admin `/admin/jobs` con CRUD + cron preview + Run now + audit. Contenedor `beat` separado en docker-compose con healthcheck. Librería `celery-sqlalchemy-scheduler` o scheduler custom (~150 líneas) — decisión Sprint 0.
- **ETL Excel/files**: openpyxl / pandas server-side; tareas Celery.
- **Storage**: **Supabase Storage** — buckets `product-images`, `product-datasheets`, `import-batches`, `exports`.
- **Reverse proxy**: **Caddy** (TLS automático).
- **Despliegue**: **Hetzner** + **Docker Compose prod** + scripts `scripts/deploy.sh`. CI/CD GitHub Actions.
- **Audit**: tabla `audit_events` + triggers Postgres + particionado mensual.
- **Grafo (opcional Fase 1.5+)**: Neo4j externo para SKU↔ficha técnica↔compatibilidades de material. No bloqueante Fase 1.
- **Observabilidad**: Sentry + Loguru/structlog + Better Stack + healthchecks `/health/live` y `/health/ready`.
- **IA-ready Fase 1**: pgvector activo (dim a definir según modelo del research spike); HNSW index reservado Fase 1.5+.

**Estructura de repos** (recomendada — ADR-036, a confirmar TI MT): repos separados estilo `hppt-iom` — `mt-pricing-frontend/` (Next.js) + `mt-pricing-backend/` (FastAPI + Celery + `supabase/migrations/`) + `mt-pricing-infra/` (`docker-compose.prod.yml` + `Caddyfile` + scripts).

## Plan de ejecución — Fase 1a + 1b (decisión adoptada)
### Sprint 0 (1 sem) — Gate
1. Stack firmado por TI MT.
2. Archivos PIM + costos entregados con muestra revisada y mapeo inicial.
3. Reglas v5.1 extraídas como pseudocódigo + golden numbers.

### Fase 1a — Datos Maestros (~6-8 sem)
- S1: PIM CRUD + i18n + traducciones + importer PIM real.
- S2: Master proveedores + importer costos + validación cruzada.
- S3: Sistema de monedas + audit trail + RBAC base + i18n UI.
- **Cierre 1a**: demo "puedo mantener catálogo y costos sin tocar Excel" — gate para 1b.

### Fase 1b — Pricing y Aprobación (~6-8 sem)
- S4: Motor de pricing + simulación what-if multi-canal/esquema.
- S5: Workflow por excepción + reglas paramétricas.
- S6: Estados de canal + connector base + shadow publish sandbox.
- S7: Hardening + parallel run + handoff TI + cutover gate.

### Workstream paralelo R&D (S0–S7)
- Sistema de comparación de productos (research).

## Personas y Cambio
- Champion en Comercial nombrado antes de S1.
- Backup operator cross-trained antes del cutover.
- Captura de conocimiento tácito: walkthroughs grabados de las sheets críticas.
- Capacitación: ≥ 2 sesiones hands-on antes del parallel run + manual operativo en español.
- SLA aprobación Gerente: < 24 h horario laboral. Delegación si ausencia > 48 h.

## Migración
- Mapping sheet-by-sheet del Excel = entregable S1.
- Lógica VBA re-implementada en código aplicación, no re-importada.
- Reglas calidad: cada SKU lleva flag `data_quality` (complete/partial/blocked).
- Los 34 + 34 SKUs hoy con problemas: owner + due-date antes del cutover.
- Excel post-import: `_ARCHIVE_YYYY-MM-DD`, read-only.
- Imágenes: probe + mirror a S3 propio MT ME; acuerdo de derechos con MT España documentado.
- FX as-of stamping por batch.

## Cutover & Rollback
- Parallel run ≥ 2 semanas; reporte diario diff.
- Gate: 100 % migrado + 0 diff por X días + audit validado en muestra + backup operator capacitado.
- Excel restorable durante 90 días.
- Playbook de publicación manual si plataforma cae el día del go-live de Fase 3.
- Last-known-good export regenerado diariamente.

## Métricas Fase 1
- Tiempo recálculo SKU N canales: < 5 s.
- Recálculo masivo catálogo (224 × 5 esquemas × 4 canales): < 60 s, 1 pantalla al Gerente.
- 100 % cambios con autor + timestamp + regla + breakdown auditables.
- 0 SKUs publicables sin aprobación.
- Cobertura traducción: EN 100 %, ES y AR ≥ 95 % en SKUs publicables.
- SKUs `complete` ≥ 90 % al cierre Fase 1.
- false-positive comparador < 2 %, false-negative < 10 %, calibración OK (si se entrega en Fase 1).
- Discrepancias precio aprobado vs exportado = 0.
- Importer ejecuta sin errores en archivo real con reporte de reconciliación.

## Visión Fase 2-4 (no Fase 1)
- **Fase 2** (T+6m): inventarios + costos operativos + facturación e-invoicing UAE-compliant + integración bidireccional con PIM/ERP MT Valves España.
- **Fase 3** (T+12m): storefront B2C UAE en vivo + connectors activos Amazon UAE (FBA + FBM) y Noon UAE; mtme.ae operativa como tienda + brand-site.
- **Fase 4** (T+18m): portal B2B con listas precio negociadas por distribuidor, descuentos por volumen, multi-divisa GCC vecinos (KSA, KW, OM, BH, QA), módulo contratos.
- **Capa IA Fase 2.5+**: match semántico SKU↔competidores con pgvector, recomendador canal/precio histórico, anomaly detection feeds.
- **Agente de reabastecimiento Fase 2.5-3**: agente autónomo que monitorea stock + velocidad de venta por canal/esquema, anticipa rotura, genera POs sugeridas a proveedor (FOB China / EU / regional), coordina logística (FBA inbound, FBM warehouse, B2B drop-ship), considera lead times multi-origen + escenarios FX/freight. Aprobación humana obligatoria antes de ejecutar.

## Roadmap GraphRAG (comparador en 3 fases)

> Documentado en ADR-038 (roadmap), ADR-039 (ontología), ADR-040 (seed materiales), ADR-041 (CDC). Supersede ADR-037.

| Fase | Ventana | Stack | Target precisión |
|------|---------|-------|------------------|
| **Fase 1** (alcance actual) | 0-3 m | RAG vectorial (pgvector + HNSW) + reglas duras + VLM judge | **85-92 %** |
| **Fase 1.5 / 2** | 3-6 m | Hybrid Graph + RAG. KG inicial Neo4j (`Producto`, `Fabricante`, `Material`, `Norma`, `Tamaño`). Seed desde compat. materiales V4 + whitelist + estándares + catálogo MT | **92-95 %** |
| **Fase 2.5 / 3** | 6-12 m | GraphRAG completo. LLM razona sobre subgrafo enriquecido (fabricante + equivalencias + normas + imagen) | **96-98 %** |

**Seeds disponibles ya** (archivos del cliente, ADR-040):

- `Compatibilidad de Materiales MT V4.xlsx` — 657 filas × 12 materiales → `HECHO_DE`, `COMPATIBLE_CON` edges.
- `MT-Catalogo.pdf` + `catalogo_mt_productos.xlsx` — 4 182 filas → `Producto`, `Serie`, `Modelo`, `Variante`.
- `PIM completo.xlsx` — 5 086 filas → `Producto` + dimensiones.
- Whitelist fabricantes (Pegler, Arco, Giacomini, Apollo, Nibco) → `Fabricante`.
- PDFs `API_598`, `ISO 7-1`, `UNE-EN_1074-3` → `Norma` + `CUMPLE_NORMA` (vía LLM extraction).

**Recurso requerido Fase 2** (flag al programa): ontólogo con experiencia PVF (procurement industrial / pipes-valves-fittings). Responsabilidad de contratación: **MT** (no BR). Trigger: cierre Fase 1 (G4). Sin este recurso, Fase 2 no debe arrancar la construcción del grafo.

## Decisiones tomadas (no re-proponer)
| Decisión | Alternativa rechazada | Por qué |
|----------|----------------------|---------|
| Build custom | Akeneo / Pimcore / Odoo / SAP B1 / NetSuite / Pricefx / Vendavo | Pricing multi-canal/esquema + workflow excepción + comparador integrado no encajan en suites genéricas; lock-in y costo total más alto |
| Single-tenant MT | Multi-tenant white-label BR | BR desarrolla para MT como cliente, no productiza |
| Aprobación por excepción | Aprobación obligatoria 2-step | Equipo de 3 personas, aprobar todo se vuelve teatro |
| Fase 1 dividida 1a + 1b | Fase 1 monolítica | Entrega valor mid-phase, reduce riesgo, gate explícito antes de 1b |
| Stack del master doc (Shopify+Supabase+Make.com) | (era el default) | Decisión del cliente: redefinir stack |
| Excel `stock_dubai_v23` ≠ source operativa | Source única Fase 1 | Aclaración usuario: Excel = demo, source real = PIM file + cost files |
| Recomendación canal "óptimo" detrás de feature flag (Fase 1) | Visible Fase 1 | No hay canales `live` en Fase 1; recomendar entre activos no aplica hasta Fase 3 |
| Sistema de comparación = research workstream | Port directo de v5.1 matcher | v5.1 falla 15 % del catálogo; trasplantar reproduce el problema |
| **Stack alineado con `hppt-iom`** (Next.js 16 + FastAPI + Supabase + Celery + Hetzner + Caddy) | Next.js full-stack + Auth.js + BullMQ + R2 + Vercel (propuesta v1.0/v1.1) | Reuso de patrones, scripts y conocimiento BR; Python permite ecosistema IA para comparador; Supabase reduce piezas (Auth + DB + Storage); Hetzner + Docker Compose abarata costo |
| **Frontend Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui (new-york)** | MUI / Chakra / Mantine | ADR-028 — alineamiento `hppt-iom` |
| **Backend FastAPI Python 3.11** | NestJS / Django / Flask / .NET | ADR-029 — tipado fuerte Pydantic + ecosistema IA + OpenAPI auto-gen |
| **Worker Celery + Redis** | BullMQ (rechazada — JS) / Dramatiq / RQ / Arq | ADR-030 — backend Python; Celery más maduro |
| **Supabase Postgres + RLS + pgvector + uuidv7** | Postgres self-host / RDS / Crunchy Bridge / Neon | ADR-031 — managed BaaS integrado con Auth + Storage |
| **Supabase Auth** | Auth.js / Keycloak / Auth0 | ADR-032 — `auth.uid()` nativo en RLS |
| **Supabase Storage** | Cloudflare R2 / S3 / MinIO | ADR-033 — RLS aplicable; menos piezas a operar |
| **Hetzner + Docker Compose prod** | Vercel / AWS ECS / Fly.io | ADR-034 — single-tenant, costo + control + alineamiento BR |
| **Caddy reverse proxy** | Nginx / Traefik | ADR-035 — TLS automático + simple |
| **Repos separados estilo `hppt-iom`** | Monorepo único | ADR-036 — pipelines simples, ownership claro; **a confirmar TI MT en S0** |
| **Neo4j externo opcional Fase 1.5+** | Postgres puro siempre / Apache AGE | ADR-037 (superseded by ADR-038) — grafo SKU↔ficha↔compat útil para cross-sell; no bloqueante Fase 1 |
| **Roadmap comparador RAG → Hybrid → GraphRAG** | GraphRAG desde Fase 1 (sobre-ingeniería) / RAG-only forever (no escala) | ADR-038 — 3 fases con targets 85-92 % → 92-95 % → 96-98 %; abstracciones desde día 1 evitan refactor |
| **Ontología KG PVF** (10 nodos + 12 edges) | Ontología minimal (insuficiente) / máxima (exceso Fase 2) | ADR-039 — punto de partida; refinable por ontólogo PVF (responsabilidad MT contratar) |
| **Compat. Materiales V4 como seed KG** | Ignorar / mantener tabla relacional | ADR-040 — 657 filas curadas son seed directo de `HECHO_DE` y `COMPATIBLE_CON` |
| **CDC Postgres ↔ Neo4j vía Supabase Realtime + Celery** | Writes duales sincrónicos / refresh batch nocturno | ADR-041 — eventual consistency + tests integridad nightly |
| **Persistencia híbrida SQLAlchemy 2.0 async (core) + supabase-py (Auth/Storage)** | supabase-py puro 1:1 con hppt-iom (sin ORM) o SQLAlchemy puro (ignorar Auth/Storage Supabase) | ADR-045 — pricing engine + comparador + audit analytics justifican ORM tipado y joins; Auth/Storage se reusan 1:1 desde hppt-iom. App conecta con rol `mt_app` que respeta RLS. Pendiente firma TI MT en S0. |
| **Celery Beat con DatabaseScheduler editable** | Beat estático en código (versionado solo via deploy) o APScheduler dual (patrón hppt completo) | ADR-046 — Gerente Comercial puede ajustar horarios de digest/KPI/FX recalc sin TI; tabla `job_definitions` + UI admin + audit trigger. +1 contenedor (beat replicas=1). Decisión librería en S0. |

## Ideas anotadas para futuro (no Fase 1)
- Agente de reabastecimiento autónomo (Fase 2.5-3).
- Embeddings semánticos SKU↔competidores (Fase 1.5+).
- Recomendador canal/precio basado en histórico (Fase 2.5+).
- Anomaly detection en feeds proveedor (Fase 2.5+).
- Dashboard "margin defense" con alertas FX/freight/customs en tiempo real (Fase 1 COULD; Fase 2 likely).
- Shadow publish a sandbox Amazon UAE / Noon UAE (Fase 1 SHOULD).

## Cuestiones abiertas a S0
- **Stack**: Next.js+Postgres propuesto pero requiere firma TI MT. Si rechazan, reescribir sección técnica.
- **Cloud / residencia**: ¿AWS / Azure / GCP / on-prem? ¿obligación residencia UAE?
- **Source real catálogo**: confirmar archivo PIM + costos al recibirse, mapear formato.
- **Threshold X% margen** para auto-approve vs pending_review: definir con Gerente Comercial.
- **TI Integración**: FTE dedicado, role-share TI MT España, o vendor externo. Quién firma RACI.
- **mtme.ae remediación**: dominio parked con SSL expirado. No bloquea Fase 1 pero gating Fase 3.
- **Dataset de calibración del comparador**: ¿quién etiqueta ≥ 50 pares para benchmark? ¿plazo S0-S2?
- **Fuente de datos competidores**: scraping (riesgo CAPTCHA) vs API pagada (Keepa, DataForSEO) vs partnership marketplace — decisión + presupuesto.

## Stakeholders y comunicación
- **Sponsor MT**: Christian — decisor final ("Decisión solicitada a Christian" en master doc).
- **Validador técnico MT**: Paula — sign-off técnico antes de Sprint 1.
- **Operador BR**: Pablo Sierra (psierra@br-innovation.com) — comunicación primaria con MT.
- **Idioma de trabajo**: Español (chat + docs internos). Datos canónicos catálogo: inglés.

## Sources reales descubiertas (carpeta `Documentos referencia de articulos/`)

| Archivo | Contenido | Estructura inspeccionada | Uso Fase 1 |
|---------|-----------|--------------------------|------------|
| `PIM completo.xlsx` | **Source primaria** del catálogo Fase 1 | 1 sheet (`sheet1`), 17 cols, **5086 filas**. Headers: `Referencia de variante`, `Cod.Intrastat - AX`, `Nombre ERP - AX`, `INDIVIDUAL EAN CODE`, weights, dimensions, EAN box, qty x box, dims caja, EAN inner, MOQ inner, X PALLET. Sin columnas multi-idioma; sin URLs imagen; sin proveedor. | Importer dedicado UC-1a-05 → `products` (identidad, dims, pesos, EAN, packaging) |
| `catalogo_mt_productos.xlsx` | Catálogo derivado (probablemente índice del PDF) | 1 sheet (`Sheet1`), 6 cols, **4182 filas**. Headers: `Sección`, `Material`, `Categoría`, `Código`, `Medida`, `Página`. | Validación cruzada vs PIM completo |
| `Copia de Compatibilidad de Materiales MT V4.xlsx` | Tabla de compatibilidades de material | 1 sheet (`Hoja1`), 14 cols, **657 filas**. Headers: `Producto`, `T (Cº)`, `Latón CW604N CW617N CW602N`, `Acero al Carbono`, `Fundición de hierro GG25 GGG40 GGG50`, `Acero Inoxidable 304 A304 A304L`, `Acero Inoxidable 316 A316 A316L`, `EPDM`, `NBR (Buna)`, `FKM FPM Vitón`, `PTFE Teflón`, `RPTFE+15% FG`, `RPTFE+15% Graphite`, link tecno-products.com. | Importer FR-MAT-01 → `material_compatibilities`; deal breakers del comparador |
| `MT-Catalogo.pdf` (18 MB) | Catálogo PDF maestro | — | Supabase Storage `product-datasheets/master/`; índice futuro |
| `MTFT_*.pdf` (0912, 4091, 4295, 5114, 647, 87) | Fichas técnicas FT (Fitting?) | 6 archivos | FR-DOC-01 → `product_datasheets` + bucket `product-datasheets` |
| `MTCE_*.pdf` (5114, 647, 87) | Fichas Compliance / Engineering specs | 3 archivos | FR-DOC-01 |
| `MTMAN_*.pdf` (4151, 5114) | Manuales | 2 archivos | FR-DOC-01 |
| `API_598_Valves_Inspection_and_Testing.pdf` | Estándar API 598 | — | `reference_standards` + bucket `product-datasheets/standards/`; contexto VLM judge |
| `ISO 7-1_1994 Threads.PDF` | Estándar ISO 7-1 | — | idem |
| `UNE-EN_1074-3=2001 VALVULAS SUMINISTRO AGUA.PDF` | Estándar EU válvulas suministro de agua | — | idem |
| `CHATBOT.docx` | Contexto para chatbot futuro | — | Archivar para Fase 2.5+ |

**Implicación arquitectónica**:
- Asociación SKU↔ficha vía sufijo numérico de filename (5114, 647, 87, 4091, 4151, 4295, 0912) — confirmar con MT en S0.
- El PIM completo.xlsx es **logístico** (dims, pesos, EAN, packaging); pricing/comercial sigue viniendo del Excel demo `stock_dubai_v23` y de archivos de costos a recibir.
- `Nombre ERP - AX` parece ser el descriptor canónico (probablemente EN o ES) — confirmar idioma.
- pgvector dim del comparador a definir según el modelo elegido en research spike (hppt-iom usa 768 con Gemini).

## Inputs preservados (rutas)
- `MT_Middle_East_Documento_Maestro (1).docx` — master doc programa completo (referencia, stack rechazado).
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/PASOS.md` — runbook demo v4.
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/data/stock_dubai_v23_PRESENTACION_2026-05-01.xlsx` — Excel demo / fixture / spec de modelo de datos.
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/MT_Pricing_Intelligence_v4.html` — demo HTML 6 MB (referente UI a evolucionar).
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/src/pricing.py` — motor v5.1 (26 KB).
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/src/match_scorer_v2.py` — comparador a rediseñar.
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/data/validator_data_v4.json` — output scraper demo (224 refs).
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/data/run_summary_v4.json` — KPIs run demo.
- `MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/data/sku_to_ficha_mapping.json` — mapping fixture.
- `_bmad-output/planning-artifacts/stage2-contextual-discovery.md` — síntesis Etapa 2 (artifact + web research).
