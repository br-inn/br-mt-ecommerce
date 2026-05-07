---
title: "Product Brief: MT Middle East — Plataforma de Datos Maestros y Pricing (Fase 1)"
status: "revision_1"
created: "2026-05-06"
updated: "2026-05-06"
inputs:
  - "MT_Middle_East_Documento_Maestro (1).docx"
  - "MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/PASOS.md"
  - "MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/data/stock_dubai_v23_PRESENTACION_2026-05-01.xlsx (datos demo)"
  - "MT_Pricing_Run_Kit/MT_Pricing_Run_Kit/MT_Pricing_Intelligence_v4.html (demo)"
  - "_bmad-output/planning-artifacts/stage2-contextual-discovery.md"
  - "Aclaraciones del usuario psierra@br-innovation.com (2026-05-06 sesión)"
  - "Documentos referencia de articulos/PIM completo.xlsx (source primaria — 5086 filas, 17 cols)"
  - "Documentos referencia de articulos/catalogo_mt_productos.xlsx (catálogo derivado — 4182 filas)"
  - "Documentos referencia de articulos/Copia de Compatibilidad de Materiales MT V4.xlsx (657 filas)"
  - "Documentos referencia de articulos/MT-Catalogo.pdf (catálogo maestro PDF, 18 MB)"
  - "Documentos referencia de articulos/MTFT_*.pdf (fichas técnicas FT: 0912, 4091, 4295, 5114, 647, 87)"
  - "Documentos referencia de articulos/MTCE_*.pdf (fichas CE: 5114, 647, 87)"
  - "Documentos referencia de articulos/MTMAN_*.pdf (manuales: 4151, 5114)"
  - "Documentos referencia de articulos/API_598_Valves_Inspection_and_Testing.pdf (estándar)"
  - "Documentos referencia de articulos/ISO 7-1_1994 Threads.PDF (estándar)"
  - "Documentos referencia de articulos/UNE-EN_1074-3=2001 VALVULAS SUMINISTRO AGUA.PDF (estándar)"
  - "Documentos referencia de articulos/CHATBOT.docx (contexto chatbot futuro Fase 2.5+)"
project_name: "mt-pricing-mdm-phase1"
phase: "1 (1a + 1b)"
program: "MT Middle East Digital Platform"
sponsor: "Christian (MT)"
technical_validator: "Paula (MT)"
operator: "Pablo Sierra (BR Innovation)"
client_relationship: "BR Innovation desarrolla para MT Middle East — single-tenant"
---

# Product Brief: MT Middle East — Plataforma de Datos Maestros y Pricing (Fase 1)

## Resumen Ejecutivo

**MT Middle East** (mtme.ae, Dubái) es la unidad GCC de **MT Valves España** y opera un catálogo de ~224 referencias de productos hidrosanitarios e industriales que debe vender en mercados de alta complejidad regulatoria y operativa: Amazon UAE (FBA y FBM), Noon UAE, distribución B2B y B2C directo. Hoy todo —catálogo, costes, precios, traducciones, esquemas de margen por canal, recomendaciones de canal— vive en un único Excel maestro (`stock_dubai_v23`) con 20+ sheets interconectadas y macros VBA para tipo de cambio EUR/AED. Cada cambio de coste o de tipo de cambio dispara un recálculo manual error-prone en N canales y N esquemas, sin trazabilidad ni control de aprobación.

La **Fase 1** construye la plataforma interna que reemplaza ese Excel por un sistema de **datos maestros** (artículos + proveedores + precios), con un **motor de pricing multi-canal/multi-esquema** que evoluciona la prueba de concepto del *Pricing Run Kit v4*, un **workflow de aprobación de precios** (Comercial propone, Gerente Comercial aprueba) y soporte para **activación asincrónica de canales** (Amazon UAE, Noon UAE, B2C, B2B saldrán en vivo en fechas distintas). Esta es la primera de cuatro fases que suman: **Fase 2** (inventarios, facturación, costos), **Fase 3** (storefront B2C + marketplaces en vivo), **Fase 4** (B2B distribuidores).

**El por qué ahora:** las enmiendas a la VAT UAE 2026, el e-invoicing en marcha y el crecimiento del e-commerce B2B en GCC (~19,5 % CAGR a 2030) hacen que tener datos maestros gobernados, auditables y publicables a múltiples canales sea infraestructura crítica, no opcional. La inversión se justifica por **dos vectores combinados**: (1) **eficiencia operativa** — eliminar horas/semana de mantenimiento de Excel y errores de pricing en cascada al cambio de coste o FX, y (2) **compliance** — auditabilidad de cada decisión de precio frente a la FTA UAE bajo el régimen 2026.

**Modelo de relación**: BR Innovation desarrolla y mantiene el sistema **para MT Middle East** como cliente. La plataforma es **single-tenant** (uso exclusivo MT), no multi-tenant ni white-label. La sociedad BR↔MT define el alcance, sponsor (Christian) y validador técnico (Paula).

## El Problema

El equipo de **Comercial Canal Online & Marketplaces** mantiene 224 SKUs en un Excel con 20+ sheets que cruzan **costes desglosados** (FOB, freight, customs, FBA fees, FBM fees, payment gateway), **precios por canal** (Amazon UAE 30 %, Noon UAE 30 %, B2B MT 40 %), **traducciones** (ES/EN/AR), **competidores whitelisted**, **estimaciones de margen y ROI** y **recomendaciones de canal** (`canal_recomendado`). Cada vez que cambia un coste o el tipo de cambio EUR/AED, hay que recalcular en cascada todos los esquemas. La trazabilidad de "quién subió este precio" o "por qué se aprobó este margen" depende de mensajes de WhatsApp y comentarios sueltos en celdas.

Síntomas concretos que ya están sobre la mesa:
- **34 de 224 SKUs (15 %)** sin match en el comparador de competencia y otros 34 sin tier de matching asignado → el dato maestro está incompleto.
- **Pricing manual en N canales × M esquemas** (FBA vs FBM, B2B vs B2C) → minutos por SKU, horas en cada actualización masiva.
- **Multi-idioma en sheets paralelas** (PIM IDIOMAS, PIM Maestro, PIM + Catálogo MERGED) → riesgo de descoordinación entre nombres ES/EN/AR.
- **Tipo de cambio EUR/AED hardcodeado en macro VBA** (1 EUR = 4,29 AED, abril/mayo 2026) → cualquier oscilación obliga a editar el macro y re-ejecutar manualmente, sin histórico de la tasa aplicada en cada decisión.
- **Demo HTML estático** (`MT_Pricing_Intelligence_v4.html`, ~6 MB) que se regenera con un pipeline de 95 minutos en un Mac local con ProtonVPN — útil para presentación, inviable como sistema de trabajo.
- **Cero workflow de aprobación**: hoy el Gerente Comercial revisa precios mirando capturas de pantalla.

El coste del *status quo* no es sólo eficiencia: cuando arranquen Amazon UAE, Noon UAE, B2C y B2B —cada uno con su propia fecha de go-live— sin un sistema gobernado, los errores de precio se publican al cliente final y la VAT UAE 2026 obliga a auditabilidad de cada decisión de precio.

## La Solución

Una **aplicación web interna** que consolida tres cosas en un solo lugar:

1. **PIM** (Product Information Management): catálogo único de SKUs con specs técnicas (DN, PN, material, tipo, familia), imágenes, multi-idioma (canónico EN + traducciones ES/AR) y estado de traducción por SKU/idioma.

2. **Master de proveedores y costes**: cada SKU tiene su línea de costes desglosada (FOB, freight, customs, fees logísticos, fees tributarios, payment fees) parametrizable por **esquema de venta** (FBA / FBM / Direct B2B / Direct B2C / Marketplace listado).

3. **Motor de pricing multi-canal**: para cada SKU, calcula precio sugerido en cada canal × esquema activos, aplica reglas (margen mínimo, bundling psicológico XX,99 / XX,49 AED, alertas de margen crítico), recomienda el **canal óptimo entre los activos** y soporta **simulación what-if** para canales aún no en vivo. Usuario propone, Gerente Comercial aprueba con un click.

El Excel maestro `stock_dubai_v23` actúa como **especificación de modelo de datos y fixture de pruebas** (sus 20+ sheets describen el detalle de campos, costes, idiomas y reglas que el negocio necesita), pero **no es la fuente operativa**: contiene **datos demo** generados durante la prueba de concepto. La fuente real del catálogo Fase 1 está por definir (candidatos: alta manual en la app, exportación puntual desde PIM MT España, o combinación). Las integraciones programadas (PIM España, feeds de proveedor, conectores Amazon/Noon/Shopify) se suman en fases posteriores sin reescribir la base.

## Qué lo hace diferente

- **Ataca el hueco real del mid-market UAE**: entre el Excel hoy y suites enterprise tipo Pricefx/Vendavo (US$ 50k-200k/año, meses de implementación) no existe nada pensado para un distribuidor de Dubái con 1k-50k SKUs, multi-canal, multi-esquema, multi-idioma EN/ES/AR.
- **Diseñado alrededor del esquema de venta**, no sólo del canal: Amazon FBA y Amazon FBM son canales con costes radicalmente distintos pero que las herramientas genéricas tratan como uno solo. Aquí son ciudadanos de primera clase del modelo de datos.
- **Activación de canal asincrónica de fábrica**: no propone precios para canales `inactive` ni interfiere con go-lives escalonados; permite simular antes de activar.
- **Trazabilidad regulatoria UAE 2026 desde el día uno**: cada precio tiene autor, aprobador, timestamp, regla aplicada, breakdown de costes — auditable para la FTA.
- **Punto de partida realista, no ingenuo**: capitaliza ~18 meses de reglas de negocio ya destiladas (motor v5.1, G1/G2, alertas) pero **rediseña el subsistema de comparación de productos** (hoy 15 % del catálogo sin match), tratado como investigación dedicada y no como "port".

## A quién sirve

**Usuarios primarios (Fase 1, internos MT Middle East):**

| Rol | Qué hace en la plataforma | Aha moment |
|------|---------------------------|------------|
| **Comercial Canal Online & Marketplaces** | Mantiene catálogo, da de alta SKUs, propone precios por canal/esquema, gestiona traducciones, dispara importes desde Excel | "Cambié un coste y los 24 precios se recalcularon solos en 3 segundos." |
| **Gerente Comercial** | Aprueba/rechaza propuestas de precio, valida márgenes por esquema (FBA/FBM/B2B/B2C), revisa alertas de margen crítico, define reglas de aprobación | "Veo en una pantalla qué cambió, quién, por qué, y apruebo el lote en 5 clicks." |
| **TI de Integración** | Configura conectores futuros (Amazon, Noon, Shopify), monitorea sincronizaciones, gestiona usuarios y permisos | "Activo Noon UAE y los precios ya están listos para publicar el día del go-live." |

**Usuarios secundarios (no Fase 1, pero el sistema los habilita):**
- Cliente final B2C UAE (Fase 3 — storefront).
- Compradores Amazon UAE / Noon (Fase 3 — vía publicación a marketplaces).
- Distribuidores B2B GCC (Fase 4).

## Criterios de Éxito

**Métricas de adopción y eficiencia (90 días post-go-live Fase 1):**
- 100 % del catálogo (224 SKUs) migrado y operado desde la plataforma; el Excel queda como sólo-importar, no fuente operativa.
- Tiempo medio de actualización de precio por canal/esquema: **de minutos a segundos** (objetivo: < 5 s para recálculo de un SKU en N canales).
- 0 SKUs publicables sin aprobación del Gerente Comercial.
- 100 % de cambios de precio con autor, timestamp, regla aplicada y breakdown de costes auditable.
- Cobertura de traducción EN canónico = 100 %; ES y AR ≥ 95 % en SKUs publicables.
- **Recálculo masivo del catálogo completo (224 SKUs × 5 esquemas × 4 canales) tras cambio de FX o coste, presentado en una pantalla al Gerente Comercial en < 60 s.**

**Métricas del sistema de comparación de productos (research workstream):**
- Tasa de **falsos positivos** en match SKU↔competidor < 2 % (medida sobre dataset etiquetado por humano).
- Tasa de **falsos negativos** < 10 % (lo que el sistema descarta y un humano sí matchearía).
- **Confianza calibrada**: cuando el sistema dice "match con 85 % confianza", debe coincidir con humano ≥ 85 % de las veces (Brier score / calibration plot).
- Cobertura: SKUs con al menos 1 candidato auditado por humano ≥ 90 % del catálogo.

**Métricas de habilitación de fases siguientes:**
- Importer Excel ejecuta sin errores en archivo maestro real.
- Modelo de datos soporta los 4 canales (B2C, B2B, Amazon, Noon) y los 5 esquemas (FBA, FBM, Direct B2C, Direct B2B, Marketplace listado) con activación independiente.
- Capacidad de simular (what-if) precio en canal `inactive` validada por el Gerente Comercial.

**Métricas de calidad de datos:**
- Cada SKU migrado lleva un flag `data_quality` (`complete` / `partial` / `blocked`); SKUs `complete` ≥ 90 % al cierre Fase 1.
- Los 34 + 34 SKUs hoy sin match / con tier `NONE` tienen owner asignado y plan de remediación documentado antes del cutover.
- Discrepancias de precio entre lo aprobado en plataforma y lo que se exporta para publicar = 0.
- Importer del Excel ejecuta sin errores en archivo maestro real con reporte de reconciliación adjunto.

## Investigación crítica: Sistema de comparación de productos

> **Este es el subsistema de mayor riesgo de Fase 1 y se gestiona como investigación dedicada, no como desarrollo lineal.**

El motor v5.1 actual usa un matcher tier-keyword (`match_scorer_v2.py`) que falla en el 15 % del catálogo. Trasplantar esa lógica reproduce el problema. Antes de comprometer arquitectura, Fase 1 debe responder con evidencia:

| Pregunta de investigación | Entregable |
|---------------------------|------------|
| **Estrategia de búsqueda** — ¿cómo se generan candidatos por SKU? (queries Amazon UAE / Noon / supplier sites; uso de specs técnicas vs nombre comercial; multi-idioma EN/AR) | Documento de estrategia de búsqueda con tasa de cobertura medida sobre las 224 referencias |
| **Sourcing de datos competidores** — ¿scraping, API oficial, datasets pagos (Keepa, DataForSEO, RapidAPI), partnerships con marketplaces? Costo, sostenibilidad, legalidad UAE | Decisión sourcing firmada con presupuesto mensual estimado |
| **Comparación de imágenes** — ¿qué LLM/modelo? (GPT-4o vision, Claude vision, Gemini, modelos abiertos como CLIP / SigLIP / open-CLIP, embeddings de Pinecone Image, AWS Rekognition). Latencia, costo por SKU, accuracy en dominio (válvulas: piezas técnicas, no productos de consumo) | Benchmark con dataset etiquetado de ≥ 50 pares true-match / true-mismatch; tabla coste-vs-accuracy |
| **Comparación de datos técnicos** — ¿reglas duras (DN, PN, material, tipo, conexión) + similitud semántica de texto? ¿Qué tolerancia? ¿Cómo penalizar discrepancias críticas (DN distinto = no-match aunque imagen coincida)? | Esquema de scoring multi-dimensional con pesos justificados, plus tabla de "deal breakers" |
| **Calibración de confianza** — ¿cómo asegurar que "85 % confianza" sea verdaderamente 85 %? (calibración Platt, isotonic, conformal prediction). Threshold de auto-match vs revisión humana | Curva de calibración + threshold operativo definido sobre dataset etiquetado |
| **Validación humana asistida** — qué UI/workflow para que un humano revise candidatos dudosos sin ser cuello de botella; integración con el flujo de aprobación de Gerente Comercial | Diseño UX de "validación rápida" + estimación de carga semanal |

**Hipótesis a validar/refutar** (no son decisiones aún):
- Combinar **embeddings de imagen + embeddings de texto técnico (`name_en + DN + PN + material + family`) + reglas duras** rinde mejor que cualquier dimensión sola.
- Los modelos de visión generales (GPT-4o, Claude) **no rinden bien en hardware industrial** sin fine-tuning o sin specs estructuradas como contexto adicional — habrá que medir.
- pgvector + HNSW alcanza con < 1 M filas pero la **decisión de embeddings es independiente del stack** (se puede empezar con OpenAI y migrar a modelo abierto sin cambiar la arquitectura).

**Implicación de cronograma**: este workstream **bloquea** el motor de pricing Fase 1 ≤ recomendación-de-canal. Si la investigación tarda más de lo esperado, Fase 1 entrega PIM + costes + pricing-sin-comparador y la comparación se difiere a Fase 1.5. **Decisión gateada en Sprint 0**.

## Alcance

**Dentro (Fase 1) — priorizado MoSCoW:**

**MUST (sin esto no hay Fase 1):**
- CRUD de **artículos** (PIM): SKU, specs técnicas, imágenes, multi-idioma EN/ES/AR con estado de traducción.
- CRUD de **proveedores** (data maestra mínima: nombre, condiciones, moneda, lead time, contacto).
- **Motor de costes** por SKU × esquema de venta (FBA, FBM, Direct B2C, Direct B2B, Marketplace) con breakdown desglosado.
- **Sistema de monedas** con **moneda base** configurable (AED por defecto, dado que opera en UAE) y **tabla de tasas de cambio** versionada hacia el resto de monedas (EUR principal, USD/SAR/etc. como crecimiento). Cada precio y coste guarda el FX vigente al momento de su aprobación.
- **Motor de pricing** multi-canal × multi-esquema con reglas (margen mínimo, bundling, alertas críticas/warning), heredado y formalizado del v5.1.
- **Simulación / what-if multi-canal** en Fase 1 (recomendación entre canales `live` queda detrás de feature flag; se valida y enciende cuando ≥2 canales lleguen a `live` en Fase 3). Función objetivo de "óptimo" a definir explícitamente: por margen vs ROI vs velocidad de rotación, dado que FBA prepaga inventario y FBM no.
- **Workflow de aprobación por excepción** (no aprobación obligatoria de cada cambio):
  - Cambios **dentro de tolerancia** (variación de margen ≤ X% configurable, por defecto 5-10 %) se **auto-aprueban** y quedan en estado `auto_approved` con autor + timestamp + diff registrado en audit trail.
  - Cambios **fuera de tolerancia** (> X%, o que cruzan umbrales críticos: margen < mínimo, alertas de pricing, cambio de regla aplicada, FX swing > Y%) entran a `pending_review` y requieren firma del Gerente Comercial.
  - State machine: `draft → auto_approved | pending_review → approved | rejected | revised → exported`.
  - **Reglas de excepción** parametrizables por canal/esquema (ej. precios B2B con tolerancia más amplia que B2C; cambios en Amazon FBA escalan siempre por costo de cambio).
  - **Bulk review**: el Gerente recibe digest diario de auto_approved + pendientes en una pantalla.
  - **Regla dura**: ninguna integración / export / publicación externa puede transmitir datos en estado distinto a `approved` o `auto_approved`. Aplica a productos, costes, precios, traducciones. Enforcement a nivel modelo (constraint DB) + runtime (connectors filtran por estado y rechazan registros no aprobados).
- **Gestión de activación de canal** (states: `inactive` / `pre_launch` / `pilot` / `live` / `paused` / `deprecated`) con transiciones RBAC-controladas y efectos en cascada (pause suprime recomendaciones, deprecate congela precios).
- **RBAC** con 3 roles base: Comercial, Gerente Comercial, TI Integración.
- **Audit trail** completo en todas las tablas críticas (precios, costes, aprobaciones).
- **i18n UI** ES + EN; **datos canónicos** en EN, traducciones ES/AR; estado de traducción por SKU/idioma.
- **Carga inicial del catálogo real** Fase 1 — fuentes confirmadas: existe **archivo PIM** + **archivos de costos de productos** (a recibir en Sprint 0). Estrategia:
  - Importer dedicado para el archivo PIM (artículos + specs + idiomas + imágenes).
  - Importer separado para archivos de costos (líneas desglosadas por SKU × esquema).
  - Validación cruzada: cada SKU del PIM debe tener costes; SKUs de costos sin PIM se reportan como huérfanos.
  - Política idéntica de FX as-of stamping por batch.
- **Importer del Excel `stock_dubai_v23` como herramienta de fixture/spec** (no como source operativo): se usa para **derivar el modelo de datos** (sheets describen relaciones y reglas), validar el motor de pricing v5.1 contra los números demo, y como dataset de pruebas. **Una vez cargado el PIM real + costos reales, el Excel demo queda archivado read-only**.

**SHOULD (entran si el cronograma lo permite, posponibles a Fase 1.5):**
- **Sistema de comparación de productos** (research workstream descrito arriba) — incluye estrategia de búsqueda, sourcing, LLM de imagen, scoring multi-dimensional, calibración de confianza, UI de validación humana.
- **Export** a CSV/XLSX en formatos pre-establecidos por canal (Amazon, Noon, Shopify-ready) — preparados pero sin push automático.
- **Shadow publish** a sandbox de Amazon UAE Seller Central / dummy ASIN para validar formato antes de Fase 3.

**COULD (nice-to-have, sin compromiso):**
- Recomendador de canal "óptimo" entre activos (encendido por feature flag cuando ≥2 canales `live` en Fase 3).
- Dashboard de "margin defense" con alertas FX/freight/customs en tiempo real.

**Fuera de Fase 1 (entran en fases posteriores):**
- Inventarios, facturación, costos operativos (Fase 2).
- Storefront B2C, conectores en vivo a Amazon UAE / Noon UAE / Shopify (Fase 3).
- Portal B2B distribuidores, contratos, listas de precio negociadas (Fase 4).
- Scraping competitivo Amazon UAE en producción (queda el actual como prueba de concepto offline).
- Integraciones API con PIM/ERP MT Valves España (Fase 2+).
- WhatsApp Business, chatbot, pgvector / embeddings semánticos.
- Recomendador IA, búsqueda semántica de SKUs (Fase 1.5+ con hooks dejados desde Fase 1).
- Identidad digital corporativa mtme.ae (responsabilidad fuera del sistema; flag al programa).

## Build vs Buy (decisión adoptada: Build)

Se evaluaron alternativas y se descartaron en favor de **build custom**:

| Opción | Por qué se descarta |
|--------|---------------------|
| Akeneo / Pimcore (PIM open-source) | Cubre PIM pero el motor de pricing multi-canal/multi-esquema, el workflow por excepción y la integración con el comparador de productos quedan fuera; encajar todo dispara complejidad de extensión y costo total |
| Odoo / NetSuite / SAP B1 | Suites integradas pero pesadas para 224 SKUs y un equipo de 3; pricing por canal/esquema requiere customización profunda; lock-in del vendor |
| Pricefx / Vendavo | Enterprise pricing — costo y tiempo de implementación inviables para mid-market UAE con catálogo curado |
| Build custom | Control total sobre modelo de datos, motor de pricing v5.1 codificado como diferencial, integración nativa con el research workstream del comparador, y reuso transparente para Fases 2-4 (inventario, B2C/marketplaces, B2B) sin licencias incrementales |

## Enfoque Técnico (alto nivel — para validar)

El stack del *master doc* (Shopify Advanced + Supabase + Make.com) se considera **descartado** y debe definirse de nuevo. Propuesta inicial sujeta a validación de TI MT y Gerente Comercial:

- **Frontend**: Next.js 15 (App Router) + React 19 + TypeScript + shadcn/ui + Tailwind. i18n con `next-intl`.
- **Backend**: Next.js Route Handlers (o NestJS si TI prefiere modular). API REST + tRPC opcional.
- **Base de datos**: PostgreSQL (managed o self-hosted; cloud TBD).
- **Auth + RBAC**: Auth.js (NextAuth) con providers email + roles propios.
- **ETL Excel**: SheetJS + ExcelJS server-side; jobs en cola (BullMQ + Redis) para imports grandes.
- **Storage de imágenes/docs**: S3-compatible (R2, MinIO o S3 según cloud).
- **Audit trail**: tabla `audit_events` + triggers Postgres en tablas críticas.
- **CI/CD**: GitHub Actions; entornos dev / staging / prod.
- **Observabilidad**: Sentry (errores), Postgres logs estructurados, dashboards básicos.
- **IA-ready (no Fase 1, pero hooks):** columnas `embedding VECTOR(1536)` reservadas; triggers preparados.

**Por qué este stack y no el del master doc:** prioriza control sobre el dato (Postgres directo vs Shopify-as-DB), evita lock-in a SaaS pesado para una herramienta interna, mantiene velocidad de desarrollo (Next.js), y deja la puerta abierta a embeddings/IA cuando haga falta sin tomar la decisión hoy. Si TI MT exige otro stack (.NET, Java, Python/Django), se ajusta esta sección — no se compromete el resto del brief.

**Pivot 2026-05-06 — alineación con `hppt-iom`**: Stack alineado con la arquitectura de referencia BR Innovation `hppt-iom` — frontend Next.js 16 + React 19 + React Compiler + Tailwind v4 + Shadcn/ui (new-york) + backend FastAPI Python 3.11 + Supabase Postgres (RLS + pgvector + uuidv7) + Supabase Auth + Supabase Storage + Celery + Redis + Hetzner + Docker Compose + Caddy (TLS automático). Detalle en `architecture-mt-pricing-mdm-phase1.md` v1.2 y ADRs 028-037.

## Plan de ejecución (Fase 1a + 1b)

**Decisión adoptada**: Fase 1 se ejecuta en **dos sub-fases** (1a + 1b) en lugar de un único bloque monolítico. Esto entrega valor utilizable a mitad de camino, reduce riesgo y permite revalidación de scope antes de comprometer 1b.

### Sprint 0 (1 semana) — Gate de arranque

Tres entregables sin los cuales Fase 1a no arranca:
1. **Stack firmado por TI MT** con criterios documentados (lenguajes/frameworks del equipo, cloud, residencia de datos UAE, presupuesto).
2. **Archivo PIM + archivos de costos** entregados por MT, con muestra revisada y mapeo inicial al modelo de datos relacional propuesto.
3. **Reglas del motor v5.1** extraídas del Excel/VBA como pseudocódigo + test fixtures con números golden — base para la decisión port-vs-rewrite.

### Fase 1a — Datos Maestros (~6-8 semanas)

Foco: el sistema sirve como **PIM + master de costes** operable, con i18n, monedas, audit trail y carga inicial. Sin pricing engine ni workflow.

| Sprint | Foco | Salida |
|--------|------|--------|
| S1 | PIM (CRUD artículos + i18n EN/ES/AR + estados de traducción) + importer del archivo PIM real | Catálogo navegable y editable en la app |
| S2 | Master de proveedores + importer de archivos de costos + validación cruzada PIM↔costos | Cada SKU tiene costes desglosados por esquema |
| S3 | Sistema de monedas (base AED + FX versionado) + audit trail + RBAC base + i18n UI ES/EN | Operación contable trazable y multilingüe |
| **Cierre 1a** | **Demo a Comercial + Gerente: "puedo mantener el catálogo y los costos en la app, sin tocar Excel"** | Decisión gate para arrancar 1b |

### Fase 1b — Pricing y Aprobación (~6-8 semanas)

Foco: motor de pricing multi-canal/multi-esquema + workflow por excepción + estados de canal + base para integraciones.

| Sprint | Foco | Salida |
|--------|------|--------|
| S4 | Motor de pricing (reglas v5.1 portadas o reescritas según S0) + simulación what-if multi-canal/esquema | Pricing reproducible vs números demo |
| S5 | Workflow de aprobación por excepción (auto_approved + pending_review + reglas paramétricas) | Cambios mayores escalan, menores fluyen |
| S6 | Estados de canal + base de connector con filtro por estado aprobado + shadow publish a sandbox marketplaces | Listo para Fase 3 sin re-trabajar |
| S7 | Hardening + parallel run con Excel demo + documentación handoff TI + cutover gate | Plataforma productiva |

### Workstream paralelo R&D — Sistema de comparación de productos (S0–S7)

Investigación dedicada (estrategia de búsqueda, sourcing, LLM de imagen, scoring multi-dimensional, calibración de confianza, UI de validación humana). Si para cierre de 1b la calibración no alcanza umbrales aceptables (false-positive ≥ 2 %, falsos negativos ≥ 10 %), se difiere a **Fase 1.5** sin bloquear el resto del Fase 1.

## Personas y Gestión del Cambio

- **Champion del cambio en Comercial Canal Online & Marketplaces**: persona nombrada antes de S1, con dedicación parcial declarada (≥ 30 % durante migración).
- **Operador de respaldo cross-trained** (de Comercial España o TI MT) con acceso a la app y conocimiento documentado del Excel — mitiga riesgo de single-point-of-failure.
- **Captura de conocimiento tácito**: walkthroughs grabados de las sheets críticas del Excel maestro, archivados como referencia.
- **Capacitación**: ≥ 2 sesiones hands-on antes del parallel run + manual operativo en español.
- **SLA de aprobación del Gerente Comercial**: turnaround < 24 h en horario laboral; delegación obligatoria si ausencia > 48 h; auto-escalado en cambios FX urgentes.
- **TI de Integración**: definir si es FTE dedicado, role-share con TI MT España, o vendor externo — RACI + % de asignación + on-call para go-live.

## Migración y Reconciliación de Datos

- **Workstream dedicado** liderado por el Champion del cambio + apoyo del autor del Excel.
- **Mapping sheet-by-sheet** del Excel a tablas relacionales como entregable de S1; lógica VBA re-implementada en código aplicación, no re-importada.
- **Reglas de calidad por SKU**: cada registro lleva flag `data_quality` (`complete` / `partial` / `blocked`). Los 34 + 34 SKUs hoy con problemas tienen owner y due-date antes del cutover.
- **Política de freeze del Excel**: tras la importación oficial, el archivo pasa a read-only (renombrado `_ARCHIVE_YYYY-MM-DD`); cualquier ajuste posterior pasa por la app.
- **Imágenes**: probe de los 224 `image_url_pim`, espejado a S3-compatible bajo control MT ME, acuerdo de derechos con MT España documentado.
- **FX as-of stamping**: cada batch importado se sella con la tasa vigente al día del export del Excel; precios pre-existentes quedan marcados `migrated, FX inferred`, no autoritativos.
- **Reconciliación**: reporte diario durante parallel run; cero diff durante N días consecutivos como criterio de cutover.

## Cutover y Rollback

- **Parallel run de ≥ 2 semanas**: cada cambio de precio se hace en ambos sistemas; reporte automático de diff diario.
- **Gate de cutover** firmado por Gerente Comercial + TI: 100 % catálogo migrado, 0 diff por X días, audit trail validado en muestra de Y aprobaciones, operador de respaldo capacitado.
- **Excel restorable durante 90 días post-cutover** como red de seguridad.
- **Playbook de publicación manual** documentado: si la plataforma cae el día del go-live de Amazon UAE / Noon, hay un procedimiento conocido para publicar precios desde el último export aprobado.
- **Last-known-good export** regenerado diariamente y archivado.

## Visión a 2-3 años

Si la Fase 1 cumple, MT Middle East tiene la **única plataforma gobernada de datos maestros y pricing** del programa. Las Fases 2-4 montan encima sin re-escribir el núcleo:

- **Fase 2 (T+6 meses)**: módulo de inventarios y costos operativos, facturación con e-invoicing UAE-compliant, conexión bidireccional con PIM/ERP MT Valves España.
- **Fase 3 (T+12 meses)**: storefront B2C UAE en vivo, conectores activos a Amazon UAE (FBA + FBM) y Noon UAE, mtme.ae operativa como tienda y como brand-site.
- **Fase 4 (T+18 meses)**: portal B2B con listas de precio negociadas por distribuidor, descuentos por volumen, soporte multi-divisa para GCC vecinos (KSA, KW, OM, BH, QA), módulo de contratos.
- **Capa IA (Fase 2.5+)**: match semántico SKU↔competidores con pgvector, recomendador de canal/precio con histórico, anomaly detection en feeds de proveedor.
- **Roadmap del comparador en 3 fases** (ADR-038): Fase 1 (RAG vectorial + reglas duras + VLM judge) target precisión **85-92 %**; Fase 1.5/2 (Hybrid Graph+RAG con knowledge graph inicial Neo4j, seed desde compatibilidad-de-materiales 657 filas + whitelist fabricantes + estándares) target **92-95 %**; Fase 2.5/3 (GraphRAG completo con LLM razonando sobre subgrafos de fabricante + equivalencias + normas + imagen) target **96-98 %**. Recurso clave Fase 2: ontólogo PVF a contratar por MT al cierre Fase 1. Detalle en ADR-038, ADR-039, ADR-040, ADR-041.
- **Agente de reabastecimiento (Fase 2.5-3)**: agente autónomo que monitorea stock + velocidad de venta por canal/esquema, anticipa rotura, genera órdenes de compra sugeridas a proveedor (FOB China / EU / regional), coordina con logística (FBA inbound, FBM warehouse, B2B drop-ship), considera lead times multi-origen y escenarios de FX/freight. Pasa por aprobación humana antes de ejecutar. Depende del módulo de inventarios (Fase 2) y de integraciones con proveedores (Fase 2+). **Requisito anotado, no en Fase 1.**

El éxito a 3 años no es "tener una plataforma" — es que MT Middle East pase de operar 224 SKUs en un Excel a operar 5.000-50.000 SKUs en GCC con un equipo del mismo tamaño, con calidad de dato y trazabilidad regulatoria que ningún competidor mid-market UAE tiene.

## Riesgos y Consideraciones

- **Dependencia del Excel maestro como única fuente Fase 1**: si la calidad del Excel se degrada durante la migración, contamina la plataforma. Mitigación: importer con validación estricta + preview de diff + bloqueo de campos editados manualmente en la app.
- **Activación asincrónica de canales** crea estados intermedios que el motor debe manejar (un SKU puede tener precio aprobado para Noon UAE pero Noon no estar `live` aún). Mitigación: estados explícitos por canal + simulación what-if.
- **VAT UAE 2026 + e-invoicing** pueden cambiar requisitos de auditoría durante el desarrollo. Mitigación: diseño audit-first; cualquier cambio normativo se traduce a más columnas, no a refactor.
- **Cambio operativo del equipo Comercial**: pasar de Excel a app es change management, no sólo software. Mitigación: paridad funcional con Excel en sprint 1, capacitación + período de doble operación.
- **Identidad digital mtme.ae caída**: no afecta Fase 1 (interna) pero bloquea Fase 3. Flag al programa para resolver en paralelo.
- **Stack TBD**: hasta que TI MT valide el enfoque técnico, hay incertidumbre en plazos. Decisión recomendada: validar stack en sprint 0 (1 semana) antes de empezar desarrollo.
