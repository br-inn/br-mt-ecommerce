---
title: "PRD — MT Middle East Master Data + Pricing (Fase 1)"
status: "draft"
version: "1.4"
created: "2026-05-06"
updated: "2026-05-06"
changelog:
  - "1.0 (2026-05-06): versión inicial PRD."
  - "1.1 (2026-05-06): integra recomendación externa al sponsor sobre comparador. Añade FR-CMP-OCR-01 (OCR sobre imágenes competidores), FR-CMP-REVIMG-01 (reverse image search fallback), FR-CMP-JUDGE-01 (VLM judge audit-grade con razonamiento natural-language) y BR-CMP-01 (deal breakers). POC 500 SKUs × 3 marketplaces con métricas reales + demos comerciales en paralelo. Reframing capa humana como infraestructura permanente (no Fase 1.5+). Fuente: recomendación externa al sponsor (2026-05-06)."
  - "1.2 (2026-05-06): Pivot stack a FastAPI + Supabase + Hetzner alineado con `hppt-iom`. Integración de fuentes reales del catálogo descubiertas en `Documentos referencia de articulos/` (PIM completo.xlsx 5086 filas, catálogo derivado, compatibilidades de material 657 filas, fichas técnicas PDF MTFT/MTCE/MTMAN, estándares API 598/ISO 7-1/UNE-EN 1074-3, MT-Catalogo.pdf, CHATBOT.docx). Nuevos FRs: FR-DOC-01 (cargar fichas técnicas PDF), FR-DOC-02 (indexar texto fichas para búsqueda semántica), FR-MAT-01 (tabla de compatibilidades de material). Sprint 0: añade inspección PIM completo + mapping a `products` schema + muestra 50 SKUs validada por Comercial MT. Estructura: repos separados estilo hppt-iom (`mt-pricing-frontend/` + `mt-pricing-backend/` + `supabase/migrations/`)."
  - "1.3 (2026-05-06): integra roadmap evolutivo del comparador RAG → Hybrid → GraphRAG (recomendación externa 2026-05-06). Añade §8.11 (targets escalonados Fase 1/2/3 con precisión 85-92 % → 92-95 % → 96-98 %), §8.12 (roadmap del knowledge graph informativo Fase 1, vinculante Fase 2: nodos, edges, seeds disponibles, ontólogo PVF como recurso). Nuevo FR-CMP-GRAPH-01 (hooks/abstracciones backend FastAPI para introducir KG sin refactor). Nuevo BR-CMP-GRAPH-01 (Cypher determinista para deal breakers Fase 2+, sin LLM en hard rules). Documentado en ADR-038 (roadmap), ADR-039 (ontología), ADR-040 (seed materiales), ADR-041 (CDC); supersede ADR-037."
  - "1.4 (2026-05-06): integra ADR-045 (persistencia híbrida SQLAlchemy 2.0 async + supabase-py) y ADR-046 (Celery Beat con DatabaseScheduler editable). Stack en §13.1 actualizado. §17 (decisiones tomadas) suma 2 filas: persistencia híbrida y schedules editables. Q-01 sigue sujeta a firma TI MT pero la decisión preliminar queda registrada como cerrada en §17."
project_name: "mt-pricing-mdm-phase1"
phase: "1 (1a + 1b)"
sponsor: "Christian (MT)"
technical_validator: "Paula (MT)"
operator: "Pablo Sierra (BR Innovation)"
inputs:
  - "_bmad-output/planning-artifacts/product-brief-mt-pricing-mdm-phase1.md"
  - "_bmad-output/planning-artifacts/product-brief-mt-pricing-mdm-phase1-distillate.md"
  - "_bmad-output/planning-artifacts/stage2-contextual-discovery.md"
  - "Documentos referencia de articulos/PIM completo.xlsx (5086 filas, 17 cols)"
  - "Documentos referencia de articulos/catalogo_mt_productos.xlsx (4182 filas)"
  - "Documentos referencia de articulos/Copia de Compatibilidad de Materiales MT V4.xlsx (657 filas)"
  - "Documentos referencia de articulos/MT-Catalogo.pdf (18 MB)"
  - "Documentos referencia de articulos/MTFT_*.pdf, MTCE_*.pdf, MTMAN_*.pdf"
  - "Documentos referencia de articulos/API_598, ISO 7-1, UNE-EN 1074-3 (estándares)"
  - "Documentos referencia de articulos/CHATBOT.docx (Fase 2.5+)"
---

# PRD — MT Middle East: Plataforma de Datos Maestros y Pricing (Fase 1)

> Documento de producto para que arquitectura y desarrollo arranquen Fase 1 sin re-derivar contexto. Lenguaje de trabajo: español. Identificadores técnicos, nombres de tablas, FRs, UCs y BRs en su forma canónica.

---

## 1. Resumen ejecutivo

**MT Middle East** (mtme.ae, Dubái), unidad GCC de **MT Valves España**, opera un catálogo inicial de **224 SKUs** hidrosanitarios e industriales con destino a Amazon UAE (FBA y FBM), Noon UAE, B2B distribuidores y B2C directo. Hoy todo el ciclo —catálogo, costes, traducciones, recomendaciones de canal y precios por esquema— vive en un único Excel maestro (`stock_dubai_v23`) con 20+ sheets y macros VBA para tipo de cambio EUR/AED. El **15 % del catálogo** queda sin match en el comparador, cada cambio de coste o FX dispara un recálculo manual en cascada de N canales × M esquemas, no hay trazabilidad de aprobaciones, y la VAT UAE 2026 + e-invoicing exigen auditabilidad nativa que el Excel no provee.

La **Fase 1** entrega una aplicación interna que reemplaza ese Excel como sistema operativo (Excel queda archivado como spec/fixture), consolidando **PIM + master de proveedores + motor de costes y pricing multi-canal/multi-esquema + workflow de aprobación por excepción** sobre una base de datos relacional gobernada (Postgres). Se entrega en **dos sub-fases** (1a Datos Maestros y 1b Pricing y Aprobación) con un Sprint 0 de gate y un workstream R&D paralelo dedicado al rediseño del **sistema de comparación de productos** (subsistema de mayor riesgo). El éxito de Fase 1 habilita Fases 2-4 (inventario, B2C+marketplaces en vivo, B2B distribuidores) sin reescribir el núcleo.

---

## 2. Visión y problema

### 2.1 Visión a 2-3 años

Que MT Middle East pase de operar 224 SKUs en un Excel a operar **5.000–50.000 SKUs en GCC** con un equipo del mismo tamaño, calidad de dato auditable y capacidad de publicar a B2C, B2B, Amazon UAE y Noon UAE desde una única fuente gobernada — diferencial que ningún competidor mid-market de UAE tiene hoy.

### 2.2 Problema concreto (status quo)

| Síntoma | Evidencia | Impacto |
|---------|-----------|---------|
| Excel monolítico como source operativa | `stock_dubai_v23` con 20+ sheets interconectadas (Resumen Ejecutivo, INVOICE ENRIQUECIDA v5, Amazon UAE 30 %, Noon UAE 30 %, B2B MT 40 %, Tarifas FBA & FBM, PIM Maestro, PIM IDIOMAS, PIM + Catálogo MERGED, Competidores, Mercado & Inversión) y macros VBA | Cualquier cambio implica recálculos manuales en cascada |
| 15 % de SKUs sin match en comparador | 34/224 sin candidato + 34 con tier `NONE` (run 2026-05-04) | Imposible recomendar canal o validar competitividad para esa franja |
| Recálculo manual al cambio de coste o FX | 1 EUR = 4,29 AED hardcodeado en macro VBA, abril/mayo 2026 | Minutos por SKU, horas en actualizaciones masivas, riesgo error |
| Sin trazabilidad de aprobaciones | "¿Quién subió este precio?" depende de WhatsApp / comentarios celdas | Incumple requisitos de auditoría VAT UAE 2026 + e-invoicing |
| Multi-idioma desincronizado | PIM IDIOMAS, PIM Maestro y PIM + Catálogo MERGED en sheets paralelas | Riesgo divergencia ES/EN/AR en publicaciones futuras |
| Demo HTML de 6 MB | Pipeline 95 min en Mac local con ProtonVPN | Útil para presentación, inviable como sistema de trabajo |
| Cero workflow de aprobación | Gerente Comercial revisa precios mirando capturas | No hay state machine ni control de excepciones |

### 2.3 Cost of doing nothing

- **Eficiencia**: horas/semana de mantenimiento de Excel y errores en cascada en cada actualización; minutos por SKU × N canales × M esquemas en cada cambio de coste o FX.
- **Compliance**: VAT UAE 2026 (efectiva 1-Ene-2026) amplía facultad FTA para denegar input-VAT en cadenas conectadas a evasión → la trazabilidad audit-first deja de ser opcional.
- **Habilitación**: sin datos maestros gobernados, los go-lives escalonados de Fase 3 (Amazon UAE, Noon UAE, B2C UAE, B2B GCC) publican errores al cliente final.
- **Escalabilidad**: el Excel no soporta el crecimiento previsto a 5k-50k SKUs; toda la arquitectura subsiguiente queda hipotecada.

### 2.4 Por qué ahora

- **Ventana regulatoria**: VAT UAE 2026 + e-invoicing phased rollout = buying window claro.
- **Mercado**: UAE B2B e-commerce ~19,5 % CAGR a 2030; > 80 % empresas UAE planean aumentar tooling digital (McKinsey 2026).
- **Competitivo**: el gap mid-market UAE entre Excel y suites enterprise (Pricefx US$ 50k-200k/año, Vendavo, Competera) está abierto y atacable.
- **Punto de partida**: ~18 meses de reglas de negocio destiladas en motor v5.1 (G1/G2, alertas, fallback tiers) listos para formalizarse.

---

## 3. Objetivos y criterios de éxito

### 3.1 Objetivos estratégicos Fase 1

1. **Reemplazar el Excel como sistema operativo** sin perder reglas de negocio.
2. **Auditabilidad audit-first** para VAT UAE 2026 desde el primer commit.
3. **Habilitar Fases 2-4** sin reescribir el núcleo (escalabilidad 224 → 50k SKUs).
4. **Reducir riesgo del comparador** mediante research workstream paralelo, no port directo.
5. **Mitigar single-point-of-failure** del usuario único Comercial vía champion + backup operator + capacitación.

### 3.2 OKRs Fase 1a — Datos Maestros

| Objetivo | Key Results |
|----------|-------------|
| **O1a.1** Catálogo gobernado fuera del Excel | KR1: 100 % de los 224 SKUs migrados al PIM en Sprint 1-2. KR2: SKUs `complete` ≥ 90 % al cierre 1a. KR3: Excel demo archivado read-only (`_ARCHIVE_YYYY-MM-DD`) post-import. |
| **O1a.2** Costos desglosados auditables por SKU × esquema | KR1: 100 % SKUs con costes por al menos 1 esquema. KR2: validación cruzada PIM↔costos sin SKUs huérfanos sin owner. |
| **O1a.3** Trazabilidad multi-moneda con FX as-of stamping | KR1: AED como base configurable y `fx_rates` versionada. KR2: 100 % de líneas de coste/precio importadas con FX as-of por batch. |
| **O1a.4** RBAC + audit trail base | KR1: 3 roles operativos (Comercial / Gerente / TI). KR2: cada cambio en `products` / `costs` registrado en `audit_events`. |
| **O1a.5** Cobertura de traducción | KR1: EN canónico = 100 % NOT NULL. KR2: ES y AR ≥ 95 % en SKUs publicables al cierre 1a. |

### 3.3 OKRs Fase 1b — Pricing y Aprobación

| Objetivo | Key Results |
|----------|-------------|
| **O1b.1** Recálculo a velocidad humana | KR1: recálculo de un SKU en N canales < 5 s. KR2: recálculo masivo (224 × 5 esquemas × 4 canales) < 60 s en 1 pantalla. |
| **O1b.2** Aprobación por excepción operando | KR1: 0 SKUs publicables sin estado `approved` o `auto_approved`. KR2: digest diario al Gerente con auto-aprobados + pendientes. KR3: SLA aprobación Gerente < 24 h en horario laboral. |
| **O1b.3** Activación de canal asincrónica | KR1: 6 estados de canal soportados (`inactive`/`pre_launch`/`pilot`/`live`/`paused`/`deprecated`). KR2: simulación what-if validada por Gerente para canal no `live`. |
| **O1b.4** Auditabilidad regulatoria | KR1: 100 % cambios de precio con autor + timestamp + regla + breakdown + aprobador. KR2: 0 discrepancias entre precio aprobado y precio exportado durante parallel run. |
| **O1b.5** Cutover ejecutado | KR1: parallel run ≥ 2 semanas con 0 diff por X días consecutivos. KR2: cutover gate firmado por Gerente Comercial + TI. |

### 3.4 OKRs workstream R&D — Comparador

| Objetivo | Key Results |
|----------|-------------|
| **OR.1** Calidad de match medible | KR1: false-positive < 2 % sobre dataset etiquetado. KR2: false-negative < 10 %. KR3: confianza calibrada (cuando dice 85 % es 85 % real ± margen). KR4: cobertura ≥ 90 % SKUs con al menos 1 candidato auditado. |

---

## 4. Personas y journeys

### 4.1 Mapa de personas

| Persona | Tipo | Cantidad esperada | Acceso | Responsabilidad principal |
|---------|------|-------------------|--------|---------------------------|
| Comercial Canal Online & Marketplaces | Primaria | 1 (con backup) | Editor catálogo + propuestas | Mantener catálogo, costes, proponer precios |
| Gerente Comercial | Primaria | 1 | Aprobador | Aprobar excepciones, definir reglas paramétricas |
| TI de Integración | Primaria | 1 (FTE / role-share / vendor — TBD S0) | Admin | Conectores, RBAC, monitoreo |
| Backup Operator | Secundaria | 1 (cross-trained) | Editor catálogo | Mitiga single-point-of-failure |
| Champion del Cambio | Secundaria | 1 (≥ 30 % dedicación) | Editor + walkthroughs | Lidera migración + captura de tácito |

### 4.2 Journey 1 — Comercial Canal Online & Marketplaces

**Contexto**: cambia el FX EUR/AED de 4,29 a 4,18 (apreciación AED). El Comercial debe re-evaluar precios.

1. Recibe notificación interna: "FX EUR/AED actualizado a 4,18 — 187 SKUs con costes en EUR afectados."
2. Entra a la app en idioma ES, navega a `Pricing > Recálculo Masivo`.
3. Selecciona "Disparar recálculo con FX 2026-06-12 / 4,18 AED".
4. La app muestra en < 60 s: 187 SKUs recalculados × 4 canales × 5 esquemas = 3.740 propuestas; 142 entran en `auto_approved` (delta margen ≤ 5 %), 45 en `pending_review` (delta > 5 % o cruzan margen mínimo).
5. Revisa los 45 pendientes en una tabla con filtros (canal, esquema, alerta).
6. Para 38 confirma "elevar a Gerente Comercial" (estado `pending_review` permanece). Para 7 ajusta manualmente (justifica) y los marca `pending_review` con comentario.
7. Cierra sesión. El digest diario se dispara a las 18:00 UAE al Gerente.

**Aha moment**: "Cambié un FX y los 3.740 precios se recalcularon solos en 47 s con regla aplicada y breakdown auditables."

### 4.3 Journey 2 — Gerente Comercial

**Contexto**: comienza el día revisando aprobaciones pendientes.

1. Abre la app, dashboard `Pricing > Mi cola`.
2. Ve un digest: "Hoy: 142 auto-aprobados (delta margen ≤ 5 %), 45 pendientes. Top razones de excepción: FX swing (32), margen mínimo (8), regla cambiada (5)."
3. Filtra "FX swing > 5 %" → 32 SKUs. Una tabla muestra: SKU, canal, esquema, precio anterior/nuevo, margen anterior/nuevo, alerta, breakdown.
4. Selecciona los 32 con bulk-select, valida muestra de 5 manualmente, aplica "Aprobar lote con justificación: variación FX legítima del día 2026-06-12".
5. Para los 13 restantes (margen mínimo + regla cambiada) revisa caso por caso.
6. Rechaza 2, aprueba 11. Los 2 rechazados vuelven a `revised` para que el Comercial corrija.
7. Firma del día queda registrada en `audit_events` con timestamp, comentario, lista de SKUs.

**Aha moment**: "Veo en una pantalla qué cambió, quién, por qué, y aprobé el lote en 5 clicks con trazabilidad."

### 4.4 Journey 3 — TI de Integración

**Contexto**: Noon UAE pasa de `pre_launch` a `pilot`.

1. Recibe ticket interno: "Activar Noon UAE en estado pilot a partir de 2026-07-01."
2. Entra a `Admin > Canales`, edita Noon UAE: estado `pre_launch` → `pilot`, schemes_supported [Marketplace], pilot_subset (subset de 30 SKUs).
3. La transición dispara validaciones: ¿hay precios `approved` para esos 30 SKUs en esquema Marketplace × Noon UAE? La app reporta: 28 OK, 2 sin precio aprobado.
4. Devuelve los 2 al Comercial vía notificación; cuando llegan a `approved`, vuelve a la pantalla de canal.
5. Activa "Generar export pilot Noon UAE" → CSV + reporte de validación. Ejecuta shadow publish a sandbox.
6. Verifica logs en `audit_events` y monitor del job en cola.

**Aha moment**: "Activé Noon en pilot y la app me dijo qué SKUs no estaban listos antes de exportar."

### 4.5 Journey 4 — Backup Operator

**Contexto**: el Comercial está de vacaciones. Llega un cambio de coste de proveedor.

1. Backup Operator inicia sesión con sus credenciales (rol Comercial heredado).
2. Sigue el manual operativo en español (`/docs/handbook-es.md`).
3. Navega a `Costos > Importar archivo` con el CSV recibido.
4. Preview muestra 12 SKUs afectados, breakdown comparado con costes vigentes, FX as-of stamping del batch.
5. Confirma; el sistema calcula nuevas propuestas en cada canal/esquema; `auto_approved` y `pending_review` se separan automáticamente.
6. Notifica al Gerente Comercial vía la app que hay 8 pendientes.

**Aha moment**: "Sin haber operado el sistema antes, completé un import de costos sin perder trazabilidad."

### 4.6 Journey 5 — Champion del Cambio

**Contexto**: durante S1, está migrando el conocimiento del Excel.

1. Abre la app y la sheet PIM Maestro del Excel en paralelo.
2. Sigue el plan de mapping sheet-by-sheet; valida que el SKU `MT-V-038-DN50-PN16` aparece igual en `products` con name_en, DN, PN, material, family.
3. Detecta una columna en Excel (`canal_recomendado`) que no estaba en el modelo y la registra como issue de migración.
4. Graba un walkthrough de 8 minutos explicando la lógica G1/G2 a TI Integración.
5. Carga al repositorio interno como referencia tácita.
6. Marca el SKU como `data_quality = complete` en la app.

**Aha moment**: "Cada sheet del Excel tiene un equivalente claro en el modelo de datos y puedo demostrarlo."

---

## 5. Modelo de dominio

### 5.1 Diccionario de términos clave

| Término | Definición |
|---------|------------|
| **PIM** | Product Information Management. Catálogo único de SKUs con specs técnicas, imágenes, multi-idioma. |
| **SKU** | Stock Keeping Unit. Identificador único interno de producto. |
| **Esquema de venta** (scheme) | Modo logístico/comercial: FBA, FBM, Direct B2C, Direct B2B, Marketplace listado. Tiene plantilla de componentes de coste distinta. |
| **Canal** (channel) | Destino comercial: Amazon UAE, Noon UAE, B2C directo, B2B distribuidores. Un canal soporta uno o varios esquemas. |
| **Tier** | Nivel de matching contra competidor: T0 brand → T2 técnico → T3 funcional → T4 product_name → T5 fallback → NONE. |
| **G1 / G2** | Grupos de agrupación de competidores (G1 = whitelist primario, G2 = secundario). |
| **FX as-of** | Tasa de cambio vigente al momento de aprobar un coste o precio; se persiste, no se recalcula al pasado. |
| **data_quality** | Flag por SKU: `complete` / `partial` / `blocked`. Gobierna publicabilidad. |
| **exception_rule** | Regla paramétrica que decide si un cambio entra a `auto_approved` o `pending_review` (ej. delta margen > X %, FX swing > Y %). |
| **pvp_min** | Precio de venta al público mínimo permitido (constraint del motor). |
| **breakdown** | Desglose contable de coste y precio (FOB, freight, customs, fees, payment fees, marketing). |
| **alerts** | Etiquetas críticas/warning emitidas por el motor (margen < mínimo, FX swing, etc.). |
| **canal_recomendado** | Sugerencia del motor entre canales `live` (feature flag, off Fase 1). |
| **shadow publish** | Export a entorno sandbox de marketplace para validar formato sin publicar al mercado real. |

### 5.2 Entidades núcleo y relaciones

```
products 1—N translations
products 1—N images
products 1—N costs (sku × scheme × supplier)
products 1—N prices (sku × channel × scheme)
products 1—1 data_quality_flag

suppliers 1—N costs
schemes 1—N costs
schemes N—M channels (compatibilidad)
channels 1—N prices
currencies 1—N fx_rates
fx_rates apply-to costs, prices (as-of stamping)

prices 1—N audit_events
costs 1—N audit_events
products 1—N audit_events
exception_rules apply-to prices (decide auto vs pending)
products 1—N competitor_listings (Fase 1.5+, embeddings reservados)
```

### 5.3 Reglas estructurales del dominio

- **EN canónico** sobre `products.name_en` es NOT NULL — fuente única de verdad para matching y publicación.
- **AED** como moneda base por defecto; configurable.
- Cada cambio de **coste** o **precio** persiste FX as-of (no se recalcula).
- Cada **price** referencia 1 channel + 1 scheme; precios diferentes por (channel, scheme) son registros independientes.
- Un **canal** sólo recibe registros con estado `approved` o `auto_approved` (regla dura).

---

## 6. Alcance Fase 1a — Datos Maestros

### 6.1 Requisitos funcionales (FR-1a)

#### FR-1a-01 — CRUD de artículos (PIM)
El sistema permite crear, leer, actualizar y desactivar SKUs con specs técnicas, imágenes, traducciones por idioma y flag `data_quality`.

**BDD**:
- **Dado** que soy Comercial autenticado **Cuando** creo un SKU con `sku`, `name_en`, `family`, `dn`, `pn`, `material`, `type`, `image_url` **Entonces** el sistema persiste el SKU con `data_quality = partial` por defecto, registra `audit_events` (autor, timestamp, "create") y devuelve el ID.
- **Dado** un SKU existente **Cuando** edito su ficha técnica (DN de 50 a 65) **Entonces** el sistema persiste el cambio, marca campos afectados, registra `audit_events` y dispara recálculo de precios dependientes (Fase 1b).
- **Dado** un SKU sin `name_en` **Cuando** intento guardar **Entonces** el sistema rechaza con error `EN canónico requerido`.

#### FR-1a-02 — Gestión de traducciones EN/ES/AR
El sistema soporta traducción por SKU × idioma (EN obligatorio, ES + AR opcionales) con estado por idioma (`pending` / `draft` / `approved`).

**BDD**:
- **Dado** un SKU con `name_en = "Brass gate valve DN50 PN16"` **Cuando** agrego la traducción ES `"Válvula de compuerta de latón DN50 PN16"` con estado `draft` **Entonces** la traducción queda persistida con `translation_status_es = draft`.
- **Dado** una traducción AR en estado `draft` **Cuando** apruebo la traducción **Entonces** el estado pasa a `approved` y queda disponible para export.
- **Dado** un SKU `publishable = true` **Cuando** consulto cobertura de traducción **Entonces** el sistema reporta porcentaje EN/ES/AR `approved`.

#### FR-1a-03 — Gestión de imágenes
El sistema admite carga manual de imágenes y mirror desde URL externa (probe + descarga al storage S3-compatible).

**BDD**:
- **Dado** un SKU con `image_url_pim` externa **Cuando** ejecuto la acción "Espejar imagen" **Entonces** el sistema descarga, valida formato, persiste en S3 bajo `mt-me-images/`, y actualiza `image_url` interna.
- **Dado** una imagen no descargable (404) **Cuando** ejecuto el probe **Entonces** el sistema marca el SKU con `image_status = broken_link` y registra el evento.

#### FR-1a-04 — CRUD de proveedores
Maestro de proveedores con datos mínimos: nombre, condiciones, moneda contractual, lead time, contacto, activo.

**BDD**:
- **Dado** que soy Comercial **Cuando** creo un proveedor "MT Valves España" con moneda EUR y lead time 45 días **Entonces** el sistema persiste y registra `audit_events`.
- **Dado** un proveedor activo con costes asociados **Cuando** intento desactivarlo **Entonces** el sistema solicita confirmación y mantiene los costes históricos.

#### FR-1a-05 — Motor de costes por SKU × esquema
Cada SKU tiene una o más líneas de coste por esquema de venta (FBA, FBM, Direct B2C, Direct B2B, Marketplace) con breakdown desglosado.

**BDD**:
- **Dado** un SKU `MT-V-038` y esquema `FBA` **Cuando** registro coste con `fob_eur=12,40, freight_eur=1,80, customs_aed=2,10, fba_fees_aed=8,50, payment_fees_pct=2,49` **Entonces** el sistema persiste, calcula `total_costes_aed` con el FX as-of vigente y registra `audit_events`.
- **Dado** un esquema FBA y un SKU sin coste asociado **Cuando** consulto "SKUs sin coste por esquema" **Entonces** el sistema devuelve la lista filtrada.

#### FR-1a-06 — Importer del archivo PIM real
Importer dedicado para PIM (artículos + specs + idiomas + imágenes) con preview, validación estricta, FX as-of stamping, y reporte de reconciliación.

**BDD**:
- **Dado** un archivo PIM válido **Cuando** ejecuto "Importar PIM" **Entonces** el sistema muestra preview con N SKUs nuevos, M actualizados, P rechazados y razones.
- **Dado** un preview confirmado **Cuando** ejecuto "Confirmar import" **Entonces** el sistema persiste con FX as-of del batch, registra `audit_events` por cada fila, y emite reporte de reconciliación.
- **Dado** un archivo con SKU duplicado **Cuando** intento importar **Entonces** el sistema rechaza la fila duplicada y la incluye en el reporte de errores.

#### FR-1a-07 — Importer de archivos de costos
Importer separado para archivos de costos (líneas desglosadas SKU × esquema × proveedor) con validación cruzada contra PIM y FX as-of stamping.

**BDD**:
- **Dado** un archivo de costos con N líneas **Cuando** ejecuto preview **Entonces** el sistema reporta SKUs huérfanos (sin PIM), esquemas desconocidos y errores de breakdown.
- **Dado** un archivo de costos confirmado **Cuando** ejecuto el import **Entonces** cada línea persiste con FX as-of del batch y `audit_events` correspondientes.

#### FR-1a-08 — Importer del Excel `stock_dubai_v23` (fixture/spec)
Importer parametrizable para extraer del Excel demo el modelo de datos como fixture de pruebas (no source operativa).

**BDD**:
- **Dado** el archivo `stock_dubai_v23` **Cuando** ejecuto el importer en modo `fixture` **Entonces** el sistema carga las sheets en tablas staging y genera reporte de mapping para validación humana.
- **Dado** que se completó el import del PIM real **Cuando** se confirme cierre Sprint 2 **Entonces** el Excel demo queda archivado read-only (`_ARCHIVE_YYYY-MM-DD`).

#### FR-1a-09 — Sistema de monedas y FX
Tabla `currencies` con base configurable (default AED) y `fx_rates` versionada (from→to, rate, effective_from, effective_to, source).

**BDD**:
- **Dado** moneda base AED **Cuando** registro `fx_rate` EUR→AED `rate=4,29 effective_from=2026-04-01` **Entonces** el sistema persiste, emite versión, y queda disponible para batches.
- **Dado** un `fx_rate` activo **Cuando** registro otro con `effective_from` posterior **Entonces** el sistema cierra el `effective_to` del anterior automáticamente.
- **Dado** un coste importado **Cuando** se persiste **Entonces** referencia el `fx_rate_id` vigente al momento (FX as-of stamping).

#### FR-1a-10 — RBAC base con 3 roles
3 roles operativos (Comercial, Gerente Comercial, TI Integración) con políticas declarativas a nivel de endpoint y entidad.

**BDD**:
- **Dado** que soy Comercial **Cuando** intento aprobar un precio (Fase 1b) **Entonces** el sistema rechaza con `403 Forbidden`.
- **Dado** que soy TI Integración **Cuando** intento editar una ficha técnica de SKU **Entonces** el sistema rechaza (write reservado a Comercial).
- **Dado** que soy Gerente Comercial **Cuando** intento crear un SKU **Entonces** el sistema lo permite (capacidad heredada para overrides).

#### FR-1a-11 — Audit trail
Tabla `audit_events` poblada por triggers en `products`, `costs`, `suppliers`, `currencies`, `fx_rates`, `translations`.

**BDD**:
- **Dado** un cambio en `products.name_en` **Cuando** se persiste **Entonces** el trigger registra `audit_events(entity='products', entity_id, field='name_en', old, new, actor, timestamp, source)`.
- **Dado** una consulta `GET /audit/products/{id}` **Cuando** la ejecuto como Gerente o TI **Entonces** el sistema devuelve histórico cronológico.

#### FR-1a-12 — i18n UI ES + EN
La interfaz soporta español e inglés con selector de usuario interno.

**BDD**:
- **Dado** un usuario con preferencia `es` **Cuando** entra a la app **Entonces** todos los strings de UI se renderizan en español.
- **Dado** un usuario que cambia a `en` **Cuando** confirma **Entonces** el cambio persiste en preferencias y la sesión recarga la UI en inglés.

#### FR-1a-13 — Validación cruzada PIM ↔ costos
Reporte que identifica SKUs en PIM sin costes y costes sin SKU en PIM (huérfanos).

**BDD**:
- **Dado** un PIM con 224 SKUs y un master de costos con 220 SKUs **Cuando** ejecuto la validación cruzada **Entonces** el sistema reporta 4 SKUs sin costes y 0 huérfanos (o viceversa) y permite asignar owner + due-date a cada uno.

#### FR-DOC-01 — Cargar fichas técnicas PDF asociadas a SKUs
El sistema permite asociar fichas técnicas en PDF (`MTFT_*`, `MTCE_*`, `MTMAN_*`) a uno o varios SKUs, almacenarlas en Supabase Storage (bucket `product-datasheets`) y mostrarlas / descargarlas desde la ficha de producto.

**BDD**:
- **Dado** un SKU `MT-V-5114` y un PDF `MTFT_5114.pdf` **Cuando** subo la ficha técnica **Entonces** el sistema persiste el archivo en `product-datasheets/MTFT_5114.pdf`, crea fila en `product_datasheets` con FK al SKU y registra `audit_events`.
- **Dado** una ficha técnica que cubre varios SKUs **Cuando** la asocio a la lista de SKUs **Entonces** el sistema crea N filas N:M sin duplicar el archivo.
- **Dado** un SKU con ficha asociada **Cuando** consulto la ficha del producto **Entonces** la app muestra el preview + botón de descarga (signed URL Supabase con TTL).

#### FR-DOC-02 — Indexar texto de fichas técnicas (búsqueda semántica futura)
Hooks para indexar el texto de las fichas técnicas mediante PDF parsing / OCR, permitiendo búsqueda semántica futura. **Activación: Fase 1.5+**. **Hooks listos: Fase 1**.

**BDD**:
- **Dado** una ficha técnica subida **Cuando** Fase 1.5+ se active el feature flag `feature.datasheet_indexing_enabled` **Entonces** una tarea Celery extrae texto via PDF parsing + OCR y lo persiste en `product_datasheet_text` con embeddings pgvector.
- **Dado** Fase 1 **Cuando** se sube una ficha **Entonces** el sistema sólo persiste el archivo y metadata; el texto NO se indexa.
- Estándares de referencia (`API 598`, `ISO 7-1`, `UNE-EN 1074-3`) son indexables igual que las fichas, almacenados en subcarpeta `standards/`.

#### FR-MAT-01 — Tabla de compatibilidades de material consultable
El sistema carga la tabla `Copia de Compatibilidad de Materiales MT V4.xlsx` (657 filas, productos × materiales × T °C) en `material_compatibilities` y la expone como referencia consultable desde la ficha de producto. Las reglas de matching del comparador (Fase 2) usan esta tabla para validar deal breakers (NPT vs BSP, SS304 vs SS316, T máx).

**BDD**:
- **Dado** la tabla `Copia de Compatibilidad de Materiales MT V4.xlsx` **Cuando** ejecuto el importer FR-MAT-01 **Entonces** el sistema persiste 657 filas en `material_compatibilities` con columnas (`producto_descriptor`, `temperatura_c`, columnas por material) y reporta filas rechazadas si las hay.
- **Dado** un SKU asociable a un descriptor de la tabla **Cuando** consulto compatibilidades **Entonces** el sistema muestra la matriz materiales × T °C aplicable.
- **Dado** Fase 2 con comparador activo y un par SKU↔candidato con materiales distintos no compatibles **Cuando** el comparador evalúa **Entonces** registra `deal_breakers_triggered = ["material_mismatch"]` consultando esta tabla.

### 6.2 Casos de uso (UC-1a)

| ID | Caso de uso | Actor | Disparador |
|----|-------------|-------|-----------|
| UC-1a-01 | Alta de SKU manual | Comercial | Necesidad de catalogar producto nuevo |
| UC-1a-02 | Edición de ficha técnica | Comercial | Spec técnica corregida |
| UC-1a-03 | Gestión de traducciones EN/ES/AR | Comercial | Cobertura insuficiente o cambio de copy |
| UC-1a-04 | Alta de proveedor | Comercial / TI | Onboarding de proveedor nuevo |
| UC-1a-05 | Importer PIM real | Comercial / TI | Carga inicial Sprint 1 |
| UC-1a-06 | Importer costos | Comercial / TI | Carga inicial Sprint 2 + actualizaciones |
| UC-1a-07 | Importer Excel fixture | TI / Champion | Fase de mapping S1 |
| UC-1a-08 | Registrar cambio FX | Comercial / TI | Actualización oficial de la tasa |
| UC-1a-09 | Validación cruzada PIM ↔ costos | Comercial | Cierre de Sprint 2 |
| UC-1a-10 | Probe + mirror de imágenes | TI | Carga inicial + mantenimiento |
| UC-1a-11 | Auditoría de cambios sobre un SKU | Gerente / TI | Investigación de discrepancia |
| UC-1a-12 | Cambio de preferencia de idioma UI | Cualquier rol | Comodidad usuario |
| UC-1a-13 | Asignación de owner a SKU `partial` o `blocked` | Champion | Plan de remediación pre-cutover |
| UC-1a-14 | Archivo del Excel demo post-import | TI / Champion | Cierre Sprint 2 |
| UC-1a-15 | Activación / desactivación de proveedor | Comercial | Cambio operativo |

### 6.3 Reglas de negocio (BR-1a)

| ID | Regla |
|----|-------|
| BR-1a-01 | `products.sku` es único globalmente; conflicto en import = rechazo de fila. |
| BR-1a-02 | `products.name_en` NOT NULL; canónico para matching y publicación. |
| BR-1a-03 | Todo SKU publicable requiere coste por al menos 1 esquema. |
| BR-1a-04 | Cada batch de import estampa FX as-of por línea (`fx_rate_id`). |
| BR-1a-05 | Costes pre-existentes migrados se marcan `migrated, fx_inferred = true`. |
| BR-1a-06 | `data_quality` por SKU: `complete` (todos los campos críticos) / `partial` / `blocked`. Sólo `complete` es publicable a marketplace. |
| BR-1a-07 | Borrar un SKU está prohibido; sólo desactivación (`active = false`). |
| BR-1a-08 | Imágenes externas se espejan a S3 propio MT ME; URLs externas no son fuente operativa. |
| BR-1a-09 | Traducciones se aprueban por idioma; sólo `approved` se exporta. |
| BR-1a-10 | Excel demo queda read-only post-import del PIM real (Sprint 2). |
| BR-1a-11 | RBAC denegación por defecto; capacidades se conceden explícitas. |
| BR-1a-12 | `audit_events` es append-only; nunca se edita ni borra. |
| BR-1a-13 | SKUs `blocked` no entran a flujo de pricing ni a exports. |
| BR-1a-14 | Cambio de FX no recalcula precios pasados (FX as-of inmutable). |
| BR-1a-15 | Validación cruzada PIM ↔ costos es entregable obligatorio cierre Sprint 2. |

---

## 7. Alcance Fase 1b — Pricing y Aprobación

### 7.1 Requisitos funcionales (FR-1b)

#### FR-1b-01 — Motor de pricing multi-canal × multi-esquema
El motor calcula precio sugerido por SKU × canal × esquema activo aplicando reglas v5.1 portadas o reescritas (decisión gateada en S0): margen mínimo, bundling psicológico (XX,99 / XX,49 AED), alertas críticas/warning, breakdown.

**BDD**:
- **Dado** un SKU con costes en esquemas FBA y FBM y canales Amazon UAE + Noon UAE en estado `pre_launch` **Cuando** ejecuto recálculo **Entonces** el sistema calcula 4 propuestas (FBA × Amazon, FBM × Amazon, FBA × Noon, FBM × Noon) con `pvp_aed`, `pvp_min`, `margin_pct`, `rule_applied`, `breakdown`, `alerts`.
- **Dado** un SKU con coste superior al `pvp_min` permitido **Cuando** se calcula **Entonces** el sistema emite `alert = critical` y la propuesta entra a `pending_review`.

#### FR-1b-02 — Simulación what-if multi-canal/esquema
El usuario puede simular precios para canales en estado distinto a `live` sin publicar.

**BDD**:
- **Dado** Noon UAE en estado `pre_launch` **Cuando** ejecuto what-if con escenario "FX = 4,18 AED" **Entonces** el sistema devuelve precios simulados sin persistir en `prices` activos.
- **Dado** un escenario what-if confirmado **Cuando** lo guardo como "escenario nombrado" **Entonces** queda disponible para comparación con el actual.

#### FR-1b-03 — Workflow de aprobación por excepción
Cambios `auto_approved` (delta margen ≤ X %, default 5-10 %, parametrizable) fluyen automáticos; el resto entra a `pending_review` y requiere firma del Gerente.

**BDD**:
- **Dado** una propuesta con delta margen 3 % **Cuando** se persiste **Entonces** estado pasa a `auto_approved` con autor + timestamp + diff registrado.
- **Dado** una propuesta con delta margen 12 % **Cuando** se persiste **Entonces** estado pasa a `pending_review`, queda en cola del Gerente, y bloquea export hasta resolución.
- **Dado** una propuesta `pending_review` **Cuando** Gerente aprueba **Entonces** estado pasa a `approved` con aprobador + timestamp + comentario.
- **Dado** una propuesta `pending_review` **Cuando** Gerente rechaza **Entonces** estado pasa a `rejected`, vuelve al Comercial como `revised`.

#### FR-1b-04 — Reglas de excepción paramétricas
Las reglas (umbrales) son configurables por canal y esquema; el sistema preserva versionado de reglas.

**BDD**:
- **Dado** que soy Gerente **Cuando** edito la regla de excepción del canal Amazon UAE × esquema FBA a "delta margen > 8 %" **Entonces** el sistema persiste la nueva versión y aplica a propuestas futuras (las pasadas mantienen la versión vigente al momento).

#### FR-1b-05 — Bulk review y digest diario
El Gerente recibe digest diario (configurable por horario) con auto_approved del día + pendientes; bulk-approve con justificación.

**BDD**:
- **Dado** las 18:00 UAE **Cuando** se ejecuta el job de digest **Entonces** el Gerente recibe en la app (y opcionalmente email) un resumen: N auto_approved, M pending_review, top razones, link directo a la cola.
- **Dado** una cola de 32 pendientes **Cuando** el Gerente aplica bulk-approve con comentario **Entonces** los 32 pasan a `approved` con el comentario asociado y `audit_events` por cada uno.

#### FR-1b-06 — Estados de canal con transiciones controladas
6 estados: `inactive` / `pre_launch` / `pilot` / `live` / `paused` / `deprecated`. Transiciones gobernadas por TI Integración.

**BDD**:
- **Dado** Noon UAE en `pre_launch` **Cuando** TI lo pasa a `pilot` con subset_skus=[…] **Entonces** el sistema valida que esos SKUs tengan precio `approved`/`auto_approved` y reporta los faltantes.
- **Dado** Amazon UAE en `live` **Cuando** TI lo pasa a `paused` **Entonces** el sistema bloquea exports activos y emite alerta a Comercial + Gerente.

#### FR-1b-07 — Regla dura de no-export sin aprobación
A nivel modelo y runtime: ningún registro sale por integración/connector si su estado ≠ `approved` ∧ ≠ `auto_approved`.

**BDD**:
- **Dado** un SKU con precio `pending_review` **Cuando** se intenta incluir en export Amazon UAE **Entonces** el sistema lo excluye automáticamente y lo reporta como "bloqueado por estado".
- **Dado** un export ejecutado **Cuando** lo audito **Entonces** todas las filas tienen estado `approved` o `auto_approved` (constraint DB y filter runtime).

#### FR-1b-08 — Export por canal/esquema (CSV/XLSX)
Exports pre-establecidos por canal: Amazon UAE, Noon UAE, Shopify-ready, B2B price list.

**BDD**:
- **Dado** un canal Amazon UAE × esquema FBA **Cuando** ejecuto "Generar export" **Entonces** el sistema produce un CSV con el formato Amazon UAE Seller Central, sólo SKUs con precio `approved`/`auto_approved`, FX as-of estampado, y archiva el último export como "last-known-good".

#### FR-1b-09 — Shadow publish a sandbox marketplaces
Capacidad de enviar exports a sandbox Amazon UAE Seller Central / dummy ASIN / Noon test environment.

**BDD**:
- **Dado** un export Amazon UAE generado **Cuando** ejecuto "Shadow publish a sandbox" **Entonces** el sistema lo carga al endpoint sandbox y captura respuesta + errores estructurados.

#### FR-1b-10 — Recomendación de canal (feature flag, off Fase 1)
Cuando ≥ 2 canales están en estado `live` (Fase 3), el sistema recomienda canal óptimo. Función objetivo (margen vs ROI vs rotación) configurable por Gerente. **Off por feature flag en Fase 1.**

**BDD**:
- **Dado** feature flag `channel_recommendation = off` **Cuando** consulto un SKU **Entonces** el sistema no muestra `canal_recomendado`.
- **Dado** feature flag `on` y 2 canales `live` **Cuando** consulto un SKU **Entonces** el sistema devuelve `canal_recomendado` con justificación.

#### FR-1b-11 — Recálculo masivo (FX o coste)
Disparable por cambio de FX o cambio de coste de proveedor.

**BDD**:
- **Dado** un cambio de FX EUR→AED **Cuando** disparo recálculo masivo **Entonces** el sistema procesa todos los SKUs afectados < 60 s y separa `auto_approved` / `pending_review`.

#### FR-1b-12 — Audit trail extendido a precios y aprobaciones
Cada cambio en `prices`, `exception_rules`, transición de canal, aprobación o rechazo queda en `audit_events`.

**BDD**:
- **Dado** una aprobación de Gerente **Cuando** se persiste **Entonces** `audit_events` registra `entity='prices', action='approve', actor=gerente_id, timestamp, comment, rule_version, fx_rate_id, breakdown_snapshot`.

#### FR-1b-13 — Escalado por inactividad del Gerente
Si una propuesta lleva > 48 h en `pending_review`, se escala (re-notificación + flag visual) y queda lista para delegación.

**BDD**:
- **Dado** una propuesta con > 48 h en `pending_review` **Cuando** se ejecuta el job de escalado **Entonces** el sistema marca `escalated = true` y notifica al delegado (configurado por Gerente).

#### FR-1b-14 — Versionado de reglas del motor
Cada cambio en `exception_rules` o reglas del motor (margen mínimo, bundling) queda versionado; cada precio referencia la versión vigente al momento de su aprobación.

**BDD**:
- **Dado** una regla "margen mínimo FBA = 25 %" v3 **Cuando** un precio es aprobado bajo esa regla **Entonces** queda con `rule_version_id = v3` y la auditoría puede reproducir la lógica.

### 7.2 Casos de uso (UC-1b)

| ID | Caso de uso | Actor | Disparador |
|----|-------------|-------|-----------|
| UC-1b-01 | Proponer precio para SKU × canal × esquema | Comercial | Cambio de coste / FX / regla |
| UC-1b-02 | Simular what-if multi-canal | Comercial / Gerente | Evaluación de escenario pre-go-live |
| UC-1b-03 | Aprobar excepción individual | Gerente | Item en `pending_review` |
| UC-1b-04 | Aprobar lote (bulk review) | Gerente | Cola homogénea (FX swing) |
| UC-1b-05 | Rechazar propuesta con comentario | Gerente | Margen insuficiente |
| UC-1b-06 | Editar regla de excepción paramétrica | Gerente | Cambio de política |
| UC-1b-07 | Cambiar estado de canal | TI Integración | Decisión de go-live / pause |
| UC-1b-08 | Generar export por canal/esquema | TI / Comercial | Distribución / pre-publish |
| UC-1b-09 | Shadow publish a sandbox | TI | Validación de formato |
| UC-1b-10 | Recálculo masivo por cambio FX | Comercial | Tasa actualizada |
| UC-1b-11 | Recálculo masivo por cambio de costes | Comercial | Nuevo archivo de costos |
| UC-1b-12 | Revisar digest diario | Gerente | Inicio de jornada |
| UC-1b-13 | Configurar delegación / escalado | Gerente | Ausencia planificada |
| UC-1b-14 | Auditar histórico de precio de SKU | Gerente / TI | Investigación / compliance |
| UC-1b-15 | Activar / desactivar feature flag (recomendación canal) | TI | Habilitación Fase 3 |

### 7.3 Reglas de negocio (BR-1b)

| ID | Regla |
|----|-------|
| BR-1b-01 | Regla dura: ningún export incluye registros con estado ≠ `approved` ∧ ≠ `auto_approved`. |
| BR-1b-02 | Auto-approve si delta margen ≤ X % (default 5-10 %, parametrizable por canal/esquema) y sin alertas críticas. |
| BR-1b-03 | Cualquier cambio que cruce `margen mínimo`, dispare alerta `critical`, cambie regla aplicada o exceda `FX swing > Y %` entra a `pending_review`. |
| BR-1b-04 | State machine: `draft → auto_approved | pending_review → approved | rejected | revised → exported`. Transiciones fuera de la máquina se rechazan. |
| BR-1b-05 | Cada precio aprobado persiste FX as-of, regla aplicada (versionada), breakdown, autor + aprobador + timestamps. |
| BR-1b-06 | Inactividad > 48 h en `pending_review` dispara escalado y alerta al delegado. |
| BR-1b-07 | Recomendación de canal entre `live` está detrás de feature flag (off Fase 1). |
| BR-1b-08 | Estados de canal sólo los puede transicionar TI Integración (RBAC). |
| BR-1b-09 | Pause de canal congela exports activos pero no los precios aprobados. |
| BR-1b-10 | Deprecate de canal congela precios y bloquea creación de propuestas nuevas. |
| BR-1b-11 | Bulk-approve requiere comentario justificativo asociado al lote. |
| BR-1b-12 | El motor no recalcula precios pasados (FX as-of inmutable); recálculo genera propuesta nueva. |
| BR-1b-13 | Reglas del motor son versionadas; cada precio referencia la versión vigente. |
| BR-1b-14 | Shadow publish nunca toca producción de marketplaces; se ejecuta sólo contra sandbox. |
| BR-1b-15 | Last-known-good export se regenera diariamente y se archiva ≥ 90 días. |

### 7.4 Workflow de aprobación por excepción — detalle

#### State machine

```
                       ┌──────────────────────────────┐
                       │            draft             │
                       └────────────┬─────────────────┘
                                    │ (engine evaluates)
            ┌───────────────────────┴───────────────────────┐
            │                                               │
            ▼                                               ▼
   ┌──────────────────┐                          ┌────────────────────┐
   │  auto_approved   │                          │  pending_review    │
   └────────┬─────────┘                          └─────┬──────────┬───┘
            │                                          │          │
            │  (no manager action needed)              │ approve  │ reject
            │                                          ▼          ▼
            │                              ┌────────────────┐ ┌──────────┐
            │                              │   approved     │ │ rejected │
            │                              └───────┬────────┘ └────┬─────┘
            │                                      │               │
            ▼                                      ▼               ▼
   ┌──────────────────────────────────────────────────────┐   revised
   │                       exported                        │   (back to Comercial)
   └──────────────────────────────────────────────────────┘
```

#### Roles y transiciones

| Transición | Origen | Destino | Actor | Trigger |
|-----------|--------|---------|-------|---------|
| Engine evaluation | draft | auto_approved | Sistema | Delta margen ≤ X %, sin alertas críticas |
| Engine evaluation | draft | pending_review | Sistema | Delta margen > X % o alerta crítica |
| Approve | pending_review | approved | Gerente | Aprobación manual |
| Reject | pending_review | rejected | Gerente | Rechazo manual con comentario |
| Revise | rejected | revised | Comercial | Edita propuesta |
| Re-evaluate | revised | draft | Sistema | Comercial confirma |
| Export | approved \| auto_approved | exported | TI | Job de export |
| Escalate | pending_review (>48h) | pending_review (escalated=true) | Sistema | Job inactividad |

#### Reglas paramétricas (ejemplos)

| Canal | Esquema | Threshold delta margen | FX swing % | Notas |
|-------|---------|------------------------|------------|-------|
| Amazon UAE | FBA | 5 % | 3 % | Costo de cambio alto, escalado siempre |
| Amazon UAE | FBM | 8 % | 5 % | Más holgura |
| Noon UAE | Marketplace | 8 % | 5 % | |
| B2B distribuidores | Direct B2B | 10 % | 7 % | Tolerancia mayor por contratos |
| B2C directo | Direct B2C | 8 % | 5 % | |

#### Ejemplo de digest diario al Gerente (2026-06-12)

```
Asunto: MT ME — Cola de precios 2026-06-12

Resumen del día:
  - 142 propuestas auto_approved (delta margen ≤ 5 %)
  - 45 pendientes de tu aprobación
  - 3 escaladas (>48h pendientes)

Top razones de excepción (pendientes):
  - FX swing > 5 % (32 propuestas) — recálculo masivo por EUR→AED 4,29 → 4,18
  - Margen mínimo FBA cruzado (8)
  - Regla aplicada cambiada (5)

Ir a la cola: https://mtme.app/pricing/queue?date=2026-06-12

Última firma: 2026-06-11 17:42 UAE — 28 aprobaciones, 1 rechazo.
```

---

## 8. Workstream paralelo R&D — Sistema de comparación de productos

### 8.1 Contexto

El motor v5.1 actual usa un matcher tier-keyword (`match_scorer_v2.py`) que falla en el **15 % del catálogo** (34/224 sin match + 34 NONE). Trasplantar reproduce el problema. Fase 1 trata el comparador como **investigación dedicada** con preguntas de evidencia y entregables medibles, no como port directo. **Si el research no llega al threshold a cierre 1b → se difiere a Fase 1.5 sin bloquear el resto.**

### 8.2 Requisitos de alto nivel

| ID | Requisito |
|----|-----------|
| R-1 | Estrategia de búsqueda: queries Amazon UAE / Noon / supplier sites por SKU, multi-idioma EN/AR, uso de specs estructuradas vs nombre comercial. Entregable: doc estrategia + tasa de cobertura medida sobre 224 SKUs. |
| R-2 | Sourcing de datos competidores: scraping vs API oficial vs datasets pagos (Keepa, DataForSEO, RapidAPI) vs partnership marketplace. Entregable: decisión sourcing firmada con presupuesto mensual. |
| R-3 | Comparación de imágenes: benchmark de ≥ 4 modelos (GPT-4o vision, Claude vision, Gemini, CLIP/SigLIP). Dataset etiquetado de ≥ 50 pares true-match / true-mismatch. Entregable: tabla coste-vs-accuracy. |
| R-4 | Comparación técnica multi-dimensional: reglas duras (DN, PN, material, tipo, conexión) + similitud semántica de texto. Entregable: esquema de scoring con pesos justificados + tabla de "deal breakers" (ej. DN distinto = no-match aunque imagen coincida). |
| R-5 | Calibración de confianza: Platt / isotonic / conformal prediction. Entregable: curva de calibración + threshold operativo. |
| R-6 | UI de validación humana: pantalla "validación rápida" como **infraestructura permanente del pipeline** (ver 8.8); integración con flujo de aprobación. Entregable: diseño UX + estimación de carga semanal + plan de optimización productividad por validador. |
| **R-7** *(v1.1)* | **OCR sobre imágenes de competidores** para extraer marca / part-number / DN / PN grabados o impresos en el cuerpo del producto. Entregable: proveedor OCR seleccionado + heurística de scoring (FR-CMP-OCR-01). |
| **R-8** *(v1.1)* | **Reverse image search** como fallback opcional cuando confidence < 0,50. Entregable: proveedor + feature flag (FR-CMP-REVIMG-01). |
| **R-9** *(v1.1)* | **VLM judge audit-grade**: el modelo de tie-break produce verdict + razonamiento natural-language + image-region pointers, almacenados y mostrados al validador humano. Entregable: schema persistencia + integración UI (FR-CMP-JUDGE-01). |
| **R-10** *(v1.1)* | **Demos comerciales en paralelo al build**: lanzar mínimo 2 demos (Intelligence Node + Skuuudle) con 200-500 SKUs MT reales, en S0. Entregable: tabla comparativa accuracy / coste / cobertura post-demo (gate G2 / G4 build-vs-buy). |

### 8.3 Métricas objetivo (gating Fase 1.5)

- **False-positive rate** < 2 % sobre dataset etiquetado.
- **False-negative rate** < 10 %.
- **Confianza calibrada**: Brier score / calibration plot dentro de margen aceptable (a definir en S0 con la curva inicial).
- **Cobertura**: ≥ 90 % SKUs con al menos 1 candidato auditado.

### 8.4 Threshold de calibración

A definir en S2 con la primera curva sobre dataset real. Hipótesis: threshold operativo `confidence ≥ 0,75` para auto-match, `0,5–0,75` para revisión humana asistida, `< 0,5` descarte.

### 8.5 Dataset etiquetado

- ≥ 50 pares true-match / true-mismatch etiquetados por humano (no datos demo).
- Owner de etiquetado + plazo asignado en S0 (cuestión abierta, sec. 20).

### 8.6 Integración con UI

- Cuando el research alcance threshold, los candidatos auditados aparecerán como "matches sugeridos" en la ficha del SKU con score y razón.
- El Comercial podrá confirmar / rechazar; cada decisión retroalimenta el dataset etiquetado.
- Integración con flujo de aprobación: matches confirmados habilitan recomendación de canal entre `live` (feature flag, off Fase 1).

### 8.7 Hipótesis a validar / refutar

- Embeddings imagen + embeddings texto técnico (`name_en + DN + PN + material + family`) + reglas duras > cualquier dimensión sola.
- Modelos visión generales no rinden bien en hardware industrial sin fine-tuning ni specs como contexto.
- pgvector + HNSW alcanza con < 1 M filas; decisión de embeddings (OpenAI vs CLIP vs SigLIP) independiente del stack.
- *(v1.1)* OCR sobre el cuerpo del producto agrega ≥ 5 puntos de F1 en el scorer cuando la imagen es legible.
- *(v1.1)* La cola humana, optimizada con UI Tinder-style + razonamiento del VLM judge, sostiene la operación a 5 000 SKUs con ≤ 1 FTE-equivalente.

### 8.8 Requisitos funcionales detallados — Comparador (v1.1)

> Sección añadida v1.1 a partir de la recomendación externa al sponsor (2026-05-06). Estos FR / BR formalizan los hooks que el spike documenta y que la arquitectura §17 implementa.

| ID | Tipo | Requisito |
|----|------|-----------|
| **FR-CMP-OCR-01** | FR | El sistema **DEBE** ejecutar OCR sobre cada imagen de competidor fetcheada (post-normalización, pre-scoring) y persistir el texto extraído como campo estructurado `competitor_listing_ocr.ocr_text`, con metadata (`ocr_provider`, `ocr_at`, `ocr_confidence`, `ocr_blocks` con bounding boxes). El scorer multi-dimensional **DEBE** consumir este campo como dimensión adicional de alto peso cuando contenga la marca esperada del SKU master o un part-number con el patrón regex de la marca. Proveedor por defecto: Google Vision OCR; fallback configurable a Tesseract self-host. Ver ADR-022. |
| **FR-CMP-REVIMG-01** | FR | El sistema **DEBE** disponer de un adapter de reverse image search activable por feature flag `feature.reverse_image_search_enabled` (default `false` Fase 1). Cuando esté activado, **DEBE** invocarse automáticamente sobre cualquier candidato cuya `calibrated_confidence` resulte `< 0,50`, antes del descarte. Proveedores soportados: TinEye API + Google Lens vía SerpAPI + Bing Visual Search. Resultado se persiste en `competitor_listings.reverse_image_hits` (JSONB). Ver ADR-023. |
| **FR-CMP-JUDGE-01** | FR | Cuando se invoque el VLM judge (Gemini 2.5 Flash o equivalente), **DEBE** retornar un payload estructurado con: `verdict ∈ {match, no_match, uncertain}`, `rationale` (texto natural 1-3 frases en idioma del operador), `image_regions` (array de bounding boxes / descripciones textuales de las regiones que motivaron la decisión) y `deal_breakers_triggered` (array de strings). Los 4 campos **DEBEN** persistirse en `match_decisions.judge_rationale`, `match_decisions.judge_image_regions`, `match_decisions.deal_breakers_triggered` y consumirse por la UI de validación humana. Ver ADR-024. |
| **FR-CMP-GRAPH-01** *(v1.3)* | FR | El backend FastAPI **DEBE** exponer el motor de comparación detrás de un puerto `ComparatorService` con adapters intercambiables (`RagOnlyComparatorAdapter` Fase 1; `HybridGraphRagAdapter` Fase 2; `FullGraphRagAdapter` Fase 3). El acceso a datos de relaciones (fabricante, material, normas, equivalencias) **DEBE** pasar por el puerto `GraphRepository` con backend `PostgresGraphRepository` Fase 1 y `Neo4jGraphRepository` Fase 2+. La introducción del knowledge graph en Fase 2 **NO DEBE** requerir refactor del orquestador del comparador ni de los endpoints de la API; solo intercambio de adapter vía configuración. Ver ADR-038, ADR-011 (IA-ready hooks). |
| **BR-CMP-01** | BR | **Deal breakers explícitos por dimensión técnica**: el sistema **NO DEBE** retornar `auto_match` ni proponer `human_pending` con confidence > 0,80 cuando se detecte cualquiera de: (a) DN distinto entre SKU y candidato; (b) PN con diferencia > 1 step de la serie estándar (PN10/16/25/40); (c) material en familias incompatibles (ej. brass vs ss316; bronze vs PVC); (d) conexión cross-family (NPT vs BSP, threaded vs flanged, threaded vs press); (e) clase de presión distinta. Aún si imagen + OCR coinciden, estos deal breakers **DEBEN** descartar el candidato y registrar el motivo en `match_candidates.hard_rules_killed_by`. |
| **BR-CMP-GRAPH-01** *(v1.3)* | BR | **Determinismo en hard rules**: el motor de comparación **DEBE** ejecutar las reglas duras (BR-CMP-01 deal breakers) sin pasar por LLM. Fase 1 las implementa como código Python sobre `products.specs` JSONB; Fase 2+ las implementa como queries Cypher sobre el knowledge graph. En ningún caso un LLM puede tomar la decisión final sobre un deal breaker. El LLM (`VLM judge`) participa solo como desempate en zona gris (BR-CMP-01 cumplido + 2+ candidatos cercanos al threshold). Ver ADR-038. |

### 8.9 POC concreto pre-cierre (refina §13.4 y §8.5)

> Añadido v1.1 a partir de la recomendación externa al sponsor (2026-05-06).

| Aspecto | Valor objetivo |
|---------|----------------|
| Tamaño POC | **500 SKUs representativos** estratificados por familia / marca / DN bin (no 50 mínimos del plan original). |
| Marketplaces | **3 simultáneos**: Amazon UAE + Noon UAE + uno de (Tradeling / Mistermart / Ubuy / fabricante directo). |
| Métricas | **Precisión y recall reales** sobre etiquetado humano del POC (no proxy); ECE; coste tecnológico real; tiempo humano por par. |
| Demos comerciales paralelas | Mismo set de 200-500 SKUs enviado a Intelligence Node + Skuuudle (mín 2; ideal 3 con Centric o DataWeave). Arrancan **en S0** por timing comercial / NDA. |
| Decision gate | Build-vs-buy con números reales en G2 (S2-S3) y G4 (S6). Ver ADR-027. |

### 8.10 Capa humana como infraestructura permanente

> Reframing v1.1 a partir de la recomendación externa al sponsor (2026-05-06). Documentado en ADR-025.

- La cola de validación humana **no es un placeholder Fase 1.5+**. Es **infraestructura permanente** del subsistema de comparación.
- KPI de éxito **no** es "% de pares auto-resueltos sin humano". KPI de éxito **es**: precisión global ≥ 99 %, productividad por validador ≥ 250 pares/hora, tiempo medio de validación ≤ 24 h SLA.
- Lectura ejecutiva: *"los líderes en este espacio (Centric, Intelligence Node, DataWeave) usan revisión humana como parte permanente del proceso. Es lo que separa el 92 % del 99 %."*
- Implicación de personal: Fase 1 contempla **1 validador freelance UAE** (10 h/sem); Fase 2+ escala con catálogo (2-3 validadores a 50k SKUs).

### 8.11 Targets escalonados Fase 1 → Fase 2 → Fase 3

> Añadido v1.3 a partir de la recomendación externa (2026-05-06). Documentado en ADR-038 y research-spike §11.

| Fase | Ventana | Stack del comparador | Target de precisión | Cómo se mide |
|------|---------|----------------------|----------------------|--------------|
| **Fase 1** (este alcance) | 0-3 m | RAG vectorial (pgvector + HNSW) + reglas duras (BR-CMP-01) + VLM judge en zona gris | **85-92 %** | FP < 2 %, FN < 10 %, ECE < 5 %, cobertura ≥ 90 % sobre dataset etiquetado del POC (500 SKUs × 3 marketplaces) |
| **Fase 1.5 / 2** | 3-6 m | Hybrid Graph + RAG. KG inicial Neo4j (`Producto`, `Fabricante`, `Material`, `Norma`, `Tamaño`). Vector top-50 → graph filter por hard constraints | **92-95 %** | mismas métricas + recall sobre cross-references entre marcas (KPI nuevo: % equivalencias correctas detectadas) |
| **Fase 2.5 / 3** | 6-12 m | GraphRAG completo. LLM razona sobre subgrafo enriquecido | **96-98 %** | mismas + reduce intervención humana ≥ 50 % vs Fase 2 |

**Implicación Fase 1**: el target 85-92 % es el gate G4 del workstream R&D. Si Fase 1 alcanza ≥ 92 %, Fase 2 se prioriza por casos de uso adicionales (cross-sell, intercambiabilidad por marca) y no solo por incremento de precisión.

### 8.12 Roadmap del knowledge graph (informativo Fase 1, vinculante Fase 2)

> Añadido v1.3 a partir de la recomendación externa (2026-05-06). Esta sección **NO compromete trabajo Fase 1**. Documenta el shape del KG para que los hooks `FR-CMP-GRAPH-01` se diseñen correctamente. Detalle completo: research-spike §11; decisión: ADR-038 / ADR-039 / ADR-040 / ADR-041.

**Nodos propuestos**: `Producto`, `Fabricante`, `Material`, `Norma`, `TipoConexion`, `ClasePresion`, `Tamaño`, `Serie`, `Modelo`, `Variante`.

**Edges propuestos**: `FABRICADO_POR`, `CUMPLE_NORMA`, `EQUIVALENTE_A`, `REEMPLAZA_A`, `COMPATIBLE_CON` (con `temp_max`), `HECHO_DE`, `TIENE_CONEXION`, `CLASE_PRESION`, `TAMAÑO`, `INSTANCIA_DE`, `PERTENECE_A_MODELO`, `PERTENECE_A_SERIE`.

**Seeds disponibles ya** (archivos del cliente):

| Archivo | Filas | Tipo de seed |
|---------|-------|--------------|
| `Compatibilidad de Materiales MT V4.xlsx` | 657 | `Material` nodos + `HECHO_DE`, `COMPATIBLE_CON` edges (ADR-040) |
| `MT-Catalogo.pdf` + `catalogo_mt_productos.xlsx` | 4 182 | `Producto`, `Serie`, `Modelo`, `Variante`, `Tamaño` nodos |
| `PIM completo.xlsx` | 5 086 | `Producto` nodos + dimensiones |
| Whitelist fabricantes (Pegler, Arco, Giacomini, Apollo, Nibco) | 5 marcas | `Fabricante` nodos |
| PDFs `API_598`, `ISO 7-1`, `UNE-EN_1074-3` | 3 normas | `Norma` nodos + `CUMPLE_NORMA` edges (vía LLM extraction) |

**Recurso requerido (flag al programa MT)**: ontólogo con experiencia PVF (procurement industrial / pipes-valves-fittings). Perfil: 5+ años industria, normas ANSI/ASME/DIN/ASTM/API/ISO, catálogos Crane/Apollo/Pegler/Giacomini, exposición a knowledge graphs. Compromiso: 60-100 % durante 2-4 m de construcción del grafo en Fase 2; 20 % maintenance Fase 3. **Responsabilidad de contratación: MT**, no BR. Trigger: cierre Fase 1 (G4). Sin este recurso, Fase 2 no debe arrancar la construcción del grafo (ver ADR-039).

---

## 9. Requisitos no funcionales (NFR)

### 9.1 Rendimiento

| ID | Requisito | Métrica |
|----|-----------|---------|
| NFR-01 | Recálculo de un SKU en N canales × M esquemas | < 5 s (p95) |
| NFR-02 | Recálculo masivo del catálogo (224 × 5 esquemas × 4 canales = 4.480 evaluaciones) | < 60 s (p95), 1 pantalla al Gerente |
| NFR-03 | Importer PIM (archivo real, ~224 filas + multi-idioma) | < 5 min (p95) |
| NFR-04 | Importer costos (archivo real, ~1.000 líneas) | < 10 min (p95) |
| NFR-05 | Generación de export por canal | < 30 s para catálogo full |
| NFR-06 | Latencia UI promedio | < 250 ms p95 en endpoints CRUD |

### 9.2 Seguridad

| ID | Requisito |
|----|-----------|
| NFR-07 | RBAC de 3 roles (Comercial, Gerente Comercial, TI Integración) con denegación por defecto. |
| NFR-08 | Auditabilidad cumpliendo VAT UAE 2026: cada cambio crítico con autor + timestamp + payload + razón. |
| NFR-09 | Residencia de datos a confirmar S0 (cloud región UAE preferente; alternativa EU si TI MT lo aprueba). |
| NFR-10 | Cifrado at-rest en DB y storage; TLS 1.2+ en tránsito. |
| NFR-11 | **Supabase Auth** (ADR-032) con providers email/password + magic link; MFA TOTP opcional Fase 1, obligatorio Fase 2 para `admin` y `gerente_comercial`. JWT verificado en backend FastAPI + RLS policies en BD (defense in depth). |
| NFR-12 | Rotación de credenciales de servicios (DB, S3, Sentry) cada 90 días. |
| NFR-13 | Logs de acceso administrativo separados (audit_admin). |

### 9.3 Disponibilidad

| ID | Requisito |
|----|-----------|
| NFR-14 | 99,5 % en horario laboral GCC (Sun-Thu 08:00–20:00 UAE). |
| NFR-15 | Ventanas de mantenimiento programadas Vie-Sáb fuera de horario. |
| NFR-16 | RTO < 4 h, RPO < 1 h en producción. |
| NFR-17 | Backups DB diarios + retención ≥ 30 días. |

### 9.4 Escalabilidad

| ID | Requisito |
|----|-----------|
| NFR-18 | Catálogo 224 → 50.000 SKUs sin re-arquitectura (paginado, índices, cola de jobs). |
| NFR-19 | Workers de cola horizontalmente escalables (**Celery + Redis**, ADR-030). |
| NFR-20 | Reservar capacidad para `embedding VECTOR(1536)` en `products` y `competitor_listings` sin coste hasta Fase 1.5. |

### 9.5 i18n

| ID | Requisito |
|----|-----------|
| NFR-21 | UI ES + EN con selector usuario; persistencia de preferencia. |
| NFR-22 | Datos canónicos en EN (NOT NULL); traducciones ES + AR opcionales con `translation_status`. |
| NFR-23 | Sin RTL UI Fase 1 (AR es contenido para export externo, no UI interna). |
| NFR-24 | Strings de UI en archivos de resources versionados (next-intl). |

### 9.6 Observabilidad

| ID | Requisito |
|----|-----------|
| NFR-25 | Sentry integrado para errores frontend + backend con sourcemaps. |
| NFR-26 | Logs estructurados (JSON) con `request_id`, `user_id`, `entity`, `action`. |
| NFR-27 | Métricas de aprobación: lag mediano del Gerente, % auto-aprobado, top razones de excepción, escaladas semanales. |
| NFR-28 | Dashboards de salud DB, cola, exports, jobs FX. |

### 9.7 Localización

| ID | Requisito |
|----|-----------|
| NFR-29 | AED como moneda base por defecto, configurable. |
| NFR-30 | `fx_rates` versionada con `effective_from`, `effective_to`, `source` y FX as-of stamping en costes y precios. |
| NFR-31 | Formatos numéricos AED con punto decimal y precisión 2; EUR con coma decimal y precisión 2 (UI sensible al locale del usuario). |
| NFR-32 | Husos: UTC en DB; UI muestra Asia/Dubai por defecto. |

### 9.8 Auditoría

| ID | Requisito |
|----|-----------|
| NFR-33 | Cada cambio de precio registra autor, timestamp, regla aplicada (con versión), breakdown completo, aprobador. |
| NFR-34 | Append-only en `audit_events`; nunca update / delete. |
| NFR-35 | Retención mínima de auditoría 7 años (alineado con VAT UAE). |
| NFR-36 | Exportable de `audit_events` como CSV firmado para FTA. |

---

## 10. Modelo de datos detallado

### 10.1 Tablas núcleo (DDL conceptual)

```sql
-- products
CREATE TABLE products (
  id BIGSERIAL PRIMARY KEY,
  sku VARCHAR(64) NOT NULL UNIQUE,
  name_en TEXT NOT NULL,
  family VARCHAR(64),
  type VARCHAR(64),
  material VARCHAR(64),
  dn INT,
  pn INT,
  specs JSONB DEFAULT '{}'::jsonb,
  image_url TEXT,
  image_status VARCHAR(32) DEFAULT 'pending',
  data_quality VARCHAR(16) NOT NULL DEFAULT 'partial',  -- complete | partial | blocked
  active BOOLEAN NOT NULL DEFAULT TRUE,
  embedding VECTOR(1536),  -- reservado Fase 1.5+
  embedding_at TIMESTAMPTZ,
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by BIGINT REFERENCES users(id),
  updated_at TIMESTAMPTZ
);
CREATE INDEX idx_products_active ON products(active);
CREATE INDEX idx_products_family ON products(family);
CREATE INDEX idx_products_dq ON products(data_quality);

-- product_translations
CREATE TABLE product_translations (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id),
  language VARCHAR(8) NOT NULL,  -- 'es' | 'ar'
  name TEXT,
  description TEXT,
  translation_status VARCHAR(16) NOT NULL DEFAULT 'pending',  -- pending | draft | approved
  approved_by BIGINT REFERENCES users(id),
  approved_at TIMESTAMPTZ,
  UNIQUE (product_id, language)
);

-- suppliers
CREATE TABLE suppliers (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(128) NOT NULL,
  contractual_currency VARCHAR(8) NOT NULL,  -- ISO 4217: EUR, AED, USD
  lead_time_days INT,
  contact JSONB,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ
);

-- schemes
CREATE TABLE schemes (
  id SERIAL PRIMARY KEY,
  code VARCHAR(32) NOT NULL UNIQUE,  -- 'FBA' | 'FBM' | 'DIRECT_B2C' | 'DIRECT_B2B' | 'MARKETPLACE'
  name VARCHAR(64) NOT NULL,
  cost_components_template JSONB NOT NULL  -- ej: ['fob', 'freight', 'customs', 'fba_fees', 'payment_fees']
);

-- channels
CREATE TABLE channels (
  id SERIAL PRIMARY KEY,
  code VARCHAR(32) NOT NULL UNIQUE,  -- 'AMAZON_UAE' | 'NOON_UAE' | 'B2C_DIRECT' | 'B2B_DIRECT'
  name VARCHAR(64) NOT NULL,
  state VARCHAR(16) NOT NULL DEFAULT 'inactive',  -- inactive | pre_launch | pilot | live | paused | deprecated
  schemes_supported INT[] NOT NULL,  -- FK array a schemes.id
  state_changed_by BIGINT REFERENCES users(id),
  state_changed_at TIMESTAMPTZ
);

-- channel_state_history
CREATE TABLE channel_state_history (
  id BIGSERIAL PRIMARY KEY,
  channel_id INT NOT NULL REFERENCES channels(id),
  from_state VARCHAR(16),
  to_state VARCHAR(16) NOT NULL,
  actor BIGINT NOT NULL REFERENCES users(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  comment TEXT
);

-- currencies
CREATE TABLE currencies (
  code VARCHAR(8) PRIMARY KEY,  -- 'AED' | 'EUR' | 'USD' | 'SAR'
  name VARCHAR(64) NOT NULL,
  is_base BOOLEAN NOT NULL DEFAULT FALSE,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

-- fx_rates
CREATE TABLE fx_rates (
  id BIGSERIAL PRIMARY KEY,
  from_currency VARCHAR(8) NOT NULL REFERENCES currencies(code),
  to_currency VARCHAR(8) NOT NULL REFERENCES currencies(code),
  rate NUMERIC(18, 6) NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  source VARCHAR(64),  -- 'manual' | 'api:openexchange' | etc.
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_fx_rates_lookup ON fx_rates(from_currency, to_currency, effective_from DESC);

-- costs
CREATE TABLE costs (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id),
  scheme_id INT NOT NULL REFERENCES schemes(id),
  supplier_id BIGINT REFERENCES suppliers(id),
  breakdown JSONB NOT NULL,  -- {fob_eur, freight_eur, customs_aed, fba_fees_aed, payment_fees_pct, marketing_aed}
  currency_origin VARCHAR(8) NOT NULL,
  total_aed NUMERIC(18, 4) NOT NULL,  -- calculado al persistir
  fx_rate_id BIGINT REFERENCES fx_rates(id),  -- FX as-of stamping
  fx_inferred BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(16) NOT NULL DEFAULT 'active',  -- active | superseded
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_costs_product_scheme ON costs(product_id, scheme_id, effective_from DESC);

-- prices
CREATE TABLE prices (
  id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(id),
  channel_id INT NOT NULL REFERENCES channels(id),
  scheme_id INT NOT NULL REFERENCES schemes(id),
  price_aed NUMERIC(18, 4) NOT NULL,
  pvp_min_aed NUMERIC(18, 4),
  margin_pct NUMERIC(8, 4),
  rule_applied VARCHAR(64),
  rule_version_id BIGINT,
  breakdown JSONB,
  alerts JSONB DEFAULT '[]'::jsonb,  -- [{level: 'critical|warning', code, message}]
  status VARCHAR(24) NOT NULL DEFAULT 'draft',
    -- draft | auto_approved | pending_review | approved | rejected | revised | exported
  proposed_by BIGINT NOT NULL REFERENCES users(id),
  proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  approved_by BIGINT REFERENCES users(id),
  approved_at TIMESTAMPTZ,
  approval_comment TEXT,
  fx_rate_id BIGINT REFERENCES fx_rates(id),  -- FX as-of stamping
  exception_rule_version_id BIGINT,
  valid_from TIMESTAMPTZ,
  valid_to TIMESTAMPTZ,
  escalated BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT prices_status_chk CHECK (status IN ('draft','auto_approved','pending_review','approved','rejected','revised','exported'))
);
CREATE INDEX idx_prices_lookup ON prices(product_id, channel_id, scheme_id, valid_from DESC);
CREATE INDEX idx_prices_status ON prices(status);
CREATE INDEX idx_prices_pending ON prices(status) WHERE status = 'pending_review';

-- exception_rules
CREATE TABLE exception_rules (
  id BIGSERIAL PRIMARY KEY,
  channel_id INT REFERENCES channels(id),  -- NULL = aplica a todos
  scheme_id INT REFERENCES schemes(id),    -- NULL = aplica a todos
  margin_delta_threshold_pct NUMERIC(6, 2) NOT NULL,  -- ej 5.00
  fx_swing_threshold_pct NUMERIC(6, 2),
  min_margin_pct NUMERIC(6, 2),
  version INT NOT NULL,
  effective_from TIMESTAMPTZ NOT NULL,
  effective_to TIMESTAMPTZ,
  created_by BIGINT NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- audit_events
CREATE TABLE audit_events (
  id BIGSERIAL PRIMARY KEY,
  entity VARCHAR(64) NOT NULL,  -- 'products' | 'costs' | 'prices' | 'channels' | ...
  entity_id BIGINT NOT NULL,
  action VARCHAR(32) NOT NULL,  -- 'create' | 'update' | 'delete' | 'approve' | 'reject' | ...
  actor BIGINT NOT NULL REFERENCES users(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload_before JSONB,
  payload_after JSONB,
  diff JSONB,
  source VARCHAR(64),  -- 'ui' | 'importer' | 'job' | 'api'
  request_id VARCHAR(64)
);
CREATE INDEX idx_audit_entity ON audit_events(entity, entity_id, changed_at DESC);
CREATE INDEX idx_audit_actor ON audit_events(actor, changed_at DESC);

-- competitor_listings (Fase 1.5+)
CREATE TABLE competitor_listings (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(32) NOT NULL,  -- 'amazon_ae' | 'noon_ae' | 'supplier_site'
  external_id VARCHAR(128) NOT NULL,  -- ASIN / Noon ID
  title TEXT,
  brand VARCHAR(64),
  price_aed NUMERIC(18, 4),
  seller VARCHAR(128),
  fba BOOLEAN,
  matched_product_id BIGINT REFERENCES products(id),
  match_score NUMERIC(6, 4),
  match_method VARCHAR(32),  -- 'tier_v51' | 'embedding_v1' | 'human'
  embedding VECTOR(1536),  -- reservado Fase 1.5+
  embedding_at TIMESTAMPTZ,
  scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source, external_id)
);

-- users
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  email VARCHAR(128) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  role VARCHAR(32) NOT NULL,  -- 'comercial' | 'gerente' | 'ti'
  ui_locale VARCHAR(8) NOT NULL DEFAULT 'es',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 10.2 Triggers de auditoría

Triggers Postgres `BEFORE UPDATE / INSERT / DELETE` en `products`, `costs`, `prices`, `suppliers`, `channels`, `currencies`, `fx_rates`, `exception_rules`, `product_translations` que persisten en `audit_events` con `payload_before` / `payload_after` / `diff`.

### 10.3 Constraints clave

- `products.sku` UNIQUE.
- `products.name_en` NOT NULL.
- `prices.status` CHECK enum.
- `(product_id, channel_id, scheme_id, valid_from)` lógicamente único para precios activos (gestionado por aplicación).
- FX as-of stamping garantizado por trigger en INSERT de `costs` y `prices` si `fx_rate_id` no fue provisto explícitamente.

---

## 11. API spec de alto nivel

### 11.1 Convenciones

- Base URL: `https://app.mtme.internal/api/v1`
- Autenticación: JWT bearer token (Supabase Auth + roles); RLS enforce en BD.
- Paginación: `?page=N&page_size=K` (max 200), `meta: { total, page, page_size }`.
- Errores estándar:
  - `400 Bad Request` — payload inválido.
  - `401 Unauthorized` — sin token.
  - `403 Forbidden` — RBAC denegado.
  - `404 Not Found` — entidad no existe.
  - `409 Conflict` — UNIQUE constraint, state machine violation.
  - `422 Unprocessable Entity` — validación de negocio (ej. EN canónico vacío).
  - `500 Internal Server Error` — error inesperado (registrado en Sentry).
- Formato error: `{ "error": { "code": "BR_1A_02", "message": "EN canónico requerido", "field": "name_en" } }`.

### 11.2 Endpoints principales

#### Productos
- `GET /products?family=&active=&data_quality=&page=` — lista paginada.
- `GET /products/{id}` — detalle.
- `POST /products` — alta. Rol: comercial.
- `PUT /products/{id}` — edición. Rol: comercial.
- `PATCH /products/{id}/data-quality` — actualiza flag. Rol: comercial.
- `POST /products/{id}/translations` — alta/edición traducción.
- `POST /products/{id}/translations/{lang}/approve` — aprueba traducción.
- `POST /products/{id}/image/probe` — probe + mirror imagen.
- `GET /products/{id}/audit` — histórico.

Ejemplo payload `POST /products`:
```json
{
  "sku": "MT-V-038-DN50-PN16",
  "name_en": "Brass gate valve DN50 PN16",
  "family": "gate_valve",
  "type": "compuerta",
  "material": "brass",
  "dn": 50,
  "pn": 16,
  "specs": { "connection": "BSP", "rating": "PN16" },
  "image_url": "https://pim.mt-valves.es/img/MT-V-038.jpg"
}
```

#### Proveedores
- `GET /suppliers`, `POST /suppliers`, `PUT /suppliers/{id}`, `PATCH /suppliers/{id}/active`.

#### Costes
- `GET /costs?product_id=&scheme_id=&active=`
- `POST /costs` — alta.
- `POST /costs/import` — importer (multipart). Rol: comercial / TI.

#### Precios
- `GET /prices?product_id=&channel_id=&scheme_id=&status=`
- `POST /prices/recalculate` — dispara recálculo (single SKU o masivo).
- `POST /prices/{id}/approve` — aprueba. Rol: gerente.
- `POST /prices/{id}/reject` — rechaza. Rol: gerente.
- `POST /prices/bulk-approve` — bulk con comentario justificativo. Rol: gerente.
- `POST /prices/simulate` — what-if (no persiste como activo).

Ejemplo `POST /prices/recalculate`:
```json
{
  "scope": "all",
  "trigger": "fx_change",
  "fx_rate_id": 1234,
  "as_of": "2026-06-12T00:00:00Z"
}
```

#### Canales
- `GET /channels`, `POST /channels/{id}/transition` (TI), `GET /channels/{id}/history`.

#### Monedas y FX
- `GET /currencies`, `GET /fx-rates`, `POST /fx-rates` (TI).

#### Reglas de excepción
- `GET /exception-rules`, `POST /exception-rules` (gerente), `GET /exception-rules/{id}/versions`.

#### Exports e integraciones
- `POST /exports/{channel_code}` — genera CSV/XLSX.
- `POST /exports/{channel_code}/shadow-publish` — sandbox.
- `GET /exports/history`.

#### Aprobación / digest
- `GET /approvals/queue?date=` — cola del Gerente.
- `GET /approvals/digest?date=` — digest diario.

#### Auditoría
- `GET /audit?entity=&entity_id=&from=&to=` — consulta filtrada.
- `GET /audit/export.csv?from=&to=` — export firmado para FTA.

#### Importers
- `POST /imports/pim` (multipart, modo `preview` | `confirm`).
- `POST /imports/costs` (multipart, modo `preview` | `confirm`).
- `POST /imports/excel-fixture` (multipart, sólo TI/Champion).
- `GET /imports/{id}/report`.

---

## 12. UX por rol (wireframes textuales)

### 12.1 Dashboard del Comercial

**Layout** (2 columnas + topbar):
- Topbar: logo MT, selector idioma ES/EN, perfil usuario.
- Sidebar izquierdo: nav (Productos / Proveedores / Costos / Precios / Importar / Auditoría / Mi cuenta).
- Main:
  - Hero: "Hola Pablo — 12 SKUs `partial`, 3 `blocked`, 8 propuestas `pending` con tu Gerente."
  - Cards rápidos: "Importar PIM", "Importar costos", "Disparar recálculo".
  - Tabla 'SKUs que requieren atención': filtros por `data_quality`, `image_status`, `translation_status`. Acciones inline (editar, asignar owner).
  - Stream "Últimas decisiones": digest de `audit_events` propios.

### 12.2 Pantalla "Editar SKU"

- Sección "Identidad": SKU (read-only), `name_en` (NOT NULL, asistido), family, type, material, DN, PN, specs JSONB editor.
- Tabs: "Imágenes" / "Traducciones" / "Costes" / "Precios" / "Auditoría".
  - Imágenes: thumbnails, botón "Probe + Mirror".
  - Traducciones: tabla EN | ES | AR con `translation_status` y botón "Aprobar".
  - Costes: tabla por esquema con breakdown JSONB y FX as-of.
  - Precios: tabla por canal × esquema con estado y diferencias.
  - Auditoría: stream cronológico.

### 12.3 Pantalla "Disparar recálculo"

- Selector "Trigger": cambio de FX / cambio de coste / manual.
- Si FX: dropdown `fx_rates` (versiones disponibles).
- Preview: "Esto afecta 187 SKUs × 4 canales × 5 esquemas = 3.740 propuestas."
- Botón "Ejecutar" con confirmación.
- Pantalla de progreso (barra + ETA), refresca cada 2 s.
- Resultado: tabla con totales por estado (`auto_approved`, `pending_review`) + link al Gerente.

### 12.4 Panel de aprobación del Gerente — Cola

**Layout**:
- Topbar: filtros rápidos (hoy / esta semana / pendientes / escaladas).
- Resumen del día (sticky): "142 auto / 45 pendientes / 3 escaladas. Top razones: FX swing 32, margen mínimo 8, regla cambiada 5."
- Tabla principal:
  - Columnas: SKU, name_en, canal, esquema, precio anterior, precio nuevo, margen anterior, margen nuevo, alerta, razón excepción, propuesto por, propuesto el, edad (h).
  - Bulk-select por checkbox.
  - Acciones: Aprobar / Rechazar / Aprobar lote con comentario.
- Sidebar derecho: detalle del item seleccionado (breakdown completo, regla aplicada, FX, audit trail).

### 12.5 Panel de aprobación del Gerente — Digest diario

- Vista de email/notificación in-app simulada en pantalla.
- Resumen día anterior + accesos rápidos a colas.
- Métricas: lag mediano de aprobación esta semana, % auto, top razones.
- Configuración del digest: hora, delegación, escalado (Mi cuenta).

### 12.6 Consola del TI Integración

**Sidebar**: Canales / Usuarios / Reglas de excepción / Importers / Exports / Logs / FX.

- **Canales**: tabla con estado, schemes_supported, último cambio, transición (botón con confirmación).
- **Usuarios**: CRUD + asignación de rol.
- **Importers**: histórico, jobs activos (cola), reportes de reconciliación descargables.
- **Exports**: histórico, último-known-good, shadow publish a sandbox (botón).
- **FX**: tabla `fx_rates` (versionada), botón "Registrar nueva tasa".
- **Logs**: stream estructurado filtrable por entity / actor / request_id.

### 12.7 Estructura del digest diario (detalle)

```
─────────────────────────────────────────────────────────
MT ME — Cola de precios — 2026-06-12 (18:00 UAE)
─────────────────────────────────────────────────────────

RESUMEN
  ✓ 142 propuestas auto-aprobadas hoy (delta margen ≤ 5 %)
  ⏳ 45 pendientes de tu aprobación
  ⚠ 3 escaladas (>48h en cola)

TOP RAZONES DE EXCEPCIÓN
  1. FX swing > 5 %               32 propuestas    [ver]
  2. Margen mínimo cruzado         8 propuestas    [ver]
  3. Regla aplicada cambiada       5 propuestas    [ver]

ESCALADAS (acción urgente)
  • SKU MT-V-122 / Amazon UAE / FBA — 56h pendiente
  • SKU MT-V-201 / Noon UAE / Marketplace — 50h
  • SKU MT-V-038 / B2B / DIRECT_B2B — 49h

ACCIONES RÁPIDAS
  [Ver cola completa] [Aprobar todas las "FX swing"]
  [Configurar delegación]

ÚLTIMA FIRMA
  2026-06-11 17:42 UAE — 28 aprobaciones, 1 rechazo.
─────────────────────────────────────────────────────────
```

---

## 13. Plan de ejecución

### 13.1 Sprint 0 — Gate de arranque (1 semana)

**Entregables**:
1. **Stack firmado por TI MT** (criterios: lenguajes/frameworks del equipo, cloud/región, residencia UAE, presupuesto). Default propuesto: **Next.js 16 + React 19 + FastAPI Python 3.11 + SQLAlchemy 2.0 async (core) + supabase-py (Auth/Storage) + Postgres Supabase + RLS + pgvector + uuidv7 + Celery + Celery Beat con DatabaseScheduler + Redis + Hetzner + Docker Compose + Caddy** (alineado con la arquitectura de referencia BR Innovation `hppt-iom`, con divergencia consciente en persistencia híbrida y scheduler editable). Ver ADRs 028-037 + ADR-045 (persistencia híbrida) + ADR-046 (DatabaseScheduler).
2. **Inspección completa de `Documentos referencia de articulos/PIM completo.xlsx`** (estructura ya verificada: 1 sheet `sheet1`, 17 columnas, ~5086 filas) **+ mapping de columnas a `products` schema + muestra de 50 SKUs validada por Comercial MT**. Mismo ejercicio para `catalogo_mt_productos.xlsx` (4182 filas, 6 columnas: Sección, Material, Categoría, Código, Medida, Página) y `Copia de Compatibilidad de Materiales MT V4.xlsx` (657 filas, 14 columnas con productos × materiales × T °C).
3. **Archivos costos** entregados con muestra revisada y mapeo inicial al modelo de datos.
4. **Reglas v5.1 extraídas** del Excel/VBA como pseudocódigo + golden numbers + tests fixture.
5. **Decisión port-vs-rewrite** del motor v5.1 (en Python — alineado con backend FastAPI).
6. **Owner + plazo** del dataset etiquetado del comparador.
7. **Threshold X %** de auto-approve definido con Gerente Comercial.
8. **TI Integración**: FTE / role-share / vendor decidido.
9. **Repos, CI/CD, entornos dev/staging/prod**: `mt-pricing-frontend/` + `mt-pricing-backend/` + repo (o carpeta) `mt-pricing-infra/` con `docker-compose.prod.yml` + `Caddyfile` + `scripts/deploy.sh`. Migrations bajo `supabase/migrations/`.
10. **Provisioning Supabase** (proyecto staging + prod) y **servidor Hetzner** (staging + prod).
11. **Confirmación residencia UAE** o aceptación de región EU (Hetzner Frankfurt/Helsinki + Supabase EU).

### 13.2 Fase 1a — Datos Maestros (~6-8 semanas)

| Sprint | Foco | Done criteria |
|--------|------|---------------|
| **S1** | PIM CRUD + i18n EN/ES/AR + traducciones + importer PIM real | Catálogo navegable; 224 SKUs cargados; EN canónico 100 %; mapping sheet-by-sheet documentado; tests de import. |
| **S2** | Master proveedores + importer costos + validación cruzada PIM↔costos | Cada SKU tiene coste por al menos 1 esquema; SKUs huérfanos reportados con owner; tests de import. |
| **S3** | Sistema de monedas + FX as-of + audit trail + RBAC base + i18n UI | AED base + EUR; `fx_rates` versionada; triggers Postgres en tablas críticas; 3 roles operativos; UI ES + EN. |
| **Cierre 1a** | Demo "puedo mantener catálogo y costos sin tocar Excel" | Gate firmado por Gerente + TI. Excel demo archivado read-only. |

### 13.3 Fase 1b — Pricing y Aprobación (~6-8 semanas)

| Sprint | Foco | Done criteria |
|--------|------|---------------|
| **S4** | Motor de pricing (port o rewrite v5.1) + simulación what-if multi-canal/esquema | Recálculo SKU < 5 s; reproducibilidad vs golden numbers; what-if disponible. |
| **S5** | Workflow por excepción + reglas paramétricas + bulk review + digest diario + escalado | State machine completa; digest funcional; reglas versionadas; SLA aprobación medible. |
| **S6** | Estados de canal + connector base con filtro de estado + shadow publish sandbox + exports por canal | 6 estados de canal; regla dura no-export sin aprobación enforced en DB y runtime; shadow publish probado. |
| **S7** | Hardening + parallel run con Excel demo + handoff TI + cutover gate + documentación operativa | Parallel run ≥ 2 semanas con 0 diff X días consecutivos; cutover firmado; manual operativo en español. |

### 13.4 Workstream paralelo R&D — Comparador (S0–S7)

| Hito | Sprint | Entregable |
|------|--------|-----------|
| H1 | S0-S1 | Estrategia de búsqueda + sourcing decidido |
| H2 | S1-S2 | Dataset etiquetado ≥ 50 pares (escala a 500 según POC §8.9) |
| H3 | S2-S3 | Benchmark de modelos (imagen + texto + OCR) |
| H4 | S3-S4 | Esquema de scoring multi-dimensional con dimensión OCR (FR-CMP-OCR-01) y deal breakers (BR-CMP-01) |
| H5 | S4-S5 | Calibración de confianza + threshold; VLM judge audit-grade (FR-CMP-JUDGE-01) operativo |
| H6 | S5-S6 | UI validación humana asistida — **infraestructura permanente** (no placeholder), muestra `judge_rationale` |
| H7 | S6-S7 | Decisión: integrar a Fase 1 o diferir a Fase 1.5 — **gate build-vs-buy con números reales** vs demos comerciales (ADR-027) |
| **H0-bis** *(v1.1)* | **S0** | **Demos comerciales en paralelo**: NDA + envío de 200-500 SKUs a Intelligence Node + Skuuudle (+ opcionalmente Centric / DataWeave) |
| **H8-OCR** *(v1.1)* | **S1-S2** | **Capa OCR** integrada (Google Vision OCR default; ADR-022); evaluación accuracy en 100 imágenes etiquetadas |
| **H9-RIS** *(v1.1)* | **S5-S6** | **Hooks reverse image search** listos detrás de feature flag (default off; ADR-023) |

---

## 14. Migración y datos

### 14.1 Mapping sheet-by-sheet del Excel demo

| Sheet Excel | Tabla destino | Notas |
|-------------|---------------|-------|
| PIM Maestro | `products` | Identidad + specs |
| PIM IDIOMAS | `product_translations` | EN canónico, ES, AR |
| PIM + Catálogo MERGED | `products` + `product_translations` | Conciliación |
| INVOICE ENRIQUECIDA v5 | `costs` (FBA / FBM) + `prices` (referencia) | Breakdown desglosado |
| REAL STOCK DUBAI INVOICE | (no Fase 1) | Reservado Fase 2 (inventario) |
| Tarifas FBA & FBM | `schemes.cost_components_template` | Plantillas de coste |
| Amazon UAE 30 % / Noon UAE 30 % / B2B MT 40 % | `prices` por canal × esquema | Datos demo |
| Macro VBA | `fx_rates` (con FX inferred = true) + lógica re-implementada en código | No re-importar VBA |
| Competidores / `competitors.json` | `competitor_listings` (Fase 1.5+) + `g1`/`g2` metadata | Reservado |
| Mercado & Inversión / Glosario / Resumen Ejecutivo | (referencia, no se importa) | Documentación |

**Entregable**: documento `docs/excel-mapping.md` aprobado al cierre Sprint 1.

### 14.2 Carga inicial del catálogo — fuentes reales descubiertas

Carpeta de referencia: `c:/BR-Github/br-mt/br-mt-ecommerce/Documentos referencia de articulos/`.

#### 14.2.1 Source primaria — `PIM completo.xlsx`

- 1 sheet (`sheet1`), **17 columnas**, **~5086 filas**.
- Headers (verificados): `Referencia de variante`, `Cod.Intrastat - AX`, `Nombre ERP - AX`, `INDIVIDUAL EAN CODE`, `weight unit`, `net weight unit`, `High mm`, `Wide mm`, `Deep mm`, `EAN CODE BOX`, `qty x box`, `Alto caja (cm) - AX`, `Ancho caja (cm) - AX`, `Largo caja (cm) - AX`, `EAN CODE INNER BOX`, `MOQ INNER BOX`, `X PALLET`.
- Observaciones:
  - **No tiene columnas multi-idioma explícitas** en este export — los campos parecen monolingüe (probablemente EN o ES). El campo `Nombre ERP - AX` es el descriptor canónico.
  - **No tiene columnas de imagen URL** explícitas en este sheet — las imágenes se gestionan aparte (PIM España) o vendrán en otro export.
  - **No tiene columnas de proveedor** — costes y proveedores vienen en archivo separado.
  - Refleja una estructura **logística** (dimensiones, pesos, EAN, packaging, MOQ, palletizing), no de pricing. → Es **complementaria** del Excel demo `stock_dubai_v23`, no equivalente.
- Importer dedicado: **UC-1a-05** mapea a `products` (campos identidad, dims, pesos, EAN); proveedores y costes via UC-1a-06.

#### 14.2.2 Catálogo derivado — `catalogo_mt_productos.xlsx`

- 1 sheet (`Sheet1`), **6 columnas**, **~4182 filas**.
- Headers: `Sección`, `Material`, `Categoría`, `Código`, `Medida`, `Página`.
- Es una **vista derivada del catálogo** (probablemente el índice del PDF maestro `MT-Catalogo.pdf`).
- Uso: validación cruzada — el `Código` debería matchear con `Referencia de variante` del PIM.
- Importer: tarea S0/S1 — generar reporte de SKUs en catálogo derivado pero ausentes en PIM completo (y viceversa).

#### 14.2.3 Tabla de compatibilidades de material — `Copia de Compatibilidad de Materiales MT V4.xlsx`

- 1 sheet (`Hoja1`), **14 columnas**, **~657 filas**.
- Headers: `Producto`, `T (Cº)`, `Latón CW604N CW617N CW602N`, `Acero al Carbono`, `Fundición de hierro GG25 GGG40 GGG50`, `Acero Inoxidable 304 A304 A304L`, `Acero Inoxidable 316 A316 A316L`, `EPDM`, `NBR (Buna)`, `FKM FPM Vitón`, `PTFE Teflón`, `RPTFE PTFE + 15% FG reforzado con Fibra de vidrio 15%`, `RPTFE  PTFE + 15% Graphite reforzado con grafito 15%`, link a `tecno-products.com/tabla-de-compatibilidad/`.
- Pasa a tabla nueva **`material_compatibilities`** en BD. Estructura conceptual:
  - `id UUID PK`, `producto_descriptor TEXT`, `temperatura_c NUMERIC`, columna por material (boolean/grado de compatibilidad), `notes TEXT`, `source_url TEXT`.
  - Alternativa normalizada: `material_compatibility_rules` con `(producto_id, material_code, temperatura_c_min/max, compatible BOOLEAN, notes)`.
- **Fase 1 nice-to-have**: cargar como referencia consultable desde la ficha de producto.
- **Fase 2 obligatorio**: las reglas de matching del comparador y de cross-sell consultan esta tabla para validar deal breakers (NPT vs BSP, SS304 vs SS316, T máx).
- Importer dedicado **FR-MAT-01**.

#### 14.2.4 Fichas técnicas PDF

Archivos detectados en la carpeta:
- **`MTFT_*.pdf`** (Fitting?): `MTFT_0912.pdf`, `MTFT_4091.pdf`, `MTFT_4295.pdf`, `MTFT_5114.pdf`, `MTFT_647.pdf`, `MTFT_87.pdf`.
- **`MTCE_*.pdf`** (Compliance / Engineering specs?): `MTCE_5114.pdf`, `MTCE_647.pdf`, `MTCE_87.pdf`.
- **`MTMAN_*.pdf`** (Manuales): `MTMAN_4151.pdf`, `MTMAN_5114.pdf`.

- Se cargan a tabla **`product_datasheets`** con FK a `products` (puede ser N:M si una ficha cubre varios SKUs).
- Se suben a **Supabase Storage** bucket `product-datasheets`.
- Indexación de texto con OCR/PDF parsing → tarea futura (Fase 1.5+, FR-DOC-02).
- Asociación SKU↔ficha vía sufijo numérico del filename (5114, 647, 87, etc.) — confirmar con MT en S0.

#### 14.2.5 Estándares de referencia

- **API 598 — Valves Inspection and Testing** (`API_598_Valves_Inspection_and_Testing.pdf`).
- **ISO 7-1:1994 Threads** (`ISO 7-1_1994 Threads.PDF`).
- **UNE-EN 1074-3:2001 Válvulas suministro de agua** (`UNE-EN_1074-3=2001 VALVULAS SUMINISTRO AGUA.PDF`).

- Metadata + storage en bucket `product-datasheets` (subcarpeta `standards/`).
- Uso: contexto técnico para el **VLM judge** (FR-CMP-JUDGE-01) y para enriquecer descripciones técnicas / matching.
- Tabla `reference_standards` con `id`, `code`, `title`, `scope`, `storage_path`, `version`, `effective_date`.

#### 14.2.6 `MT-Catalogo.pdf` (18 MB)

- Catálogo PDF maestro.
- Subir a Supabase Storage bucket `product-datasheets/master/`.
- Indexar para búsqueda futura (Fase 1.5+).

#### 14.2.7 `CHATBOT.docx`

- Contexto para chatbot futuro (Fase 2.5+).
- No procesar Fase 1; archivar en bucket `product-datasheets/future/` con flag.

#### 14.2.8 Validación cruzada y reporte de reconciliación

- SKUs PIM completo sin coste = reportados.
- SKUs en costos sin PIM = huérfanos reportables.
- SKUs en catálogo derivado sin PIM = huérfanos reportables.
- Reporte de reconciliación adjunto a cada batch.

#### 14.2.9 Importers Fase 1

- **UC-1a-05**: `PIM completo.xlsx` → `products`.
- **UC-1a-06**: archivos costos → `costs`.
- **FR-MAT-01**: `Copia de Compatibilidad de Materiales MT V4.xlsx` → `material_compatibilities`.
- **FR-DOC-01**: PDFs `MTFT/MTCE/MTMAN/standards/MT-Catalogo` → `product_datasheets` + Supabase Storage.

### 14.3 Política de freeze del Excel post-import

- Tras la importación oficial del PIM real (cierre S2), el Excel `stock_dubai_v23` pasa a read-only renombrado `_ARCHIVE_2026-MM-DD`.
- Cualquier ajuste posterior del catálogo o costos pasa por la app.
- El Excel se mantiene **restorable durante 90 días post-cutover** como red de seguridad.

### 14.4 Tratamiento de los 34 + 34 SKUs problemáticos

- **34 sin match** + **34 con tier NONE** = 68 SKUs (~30 % superpuestos).
- Cada uno: owner + due-date asignado en S1 (gestionado por Champion del Cambio).
- Se cargan al PIM con `data_quality = partial` o `blocked` según severidad.
- Plan de remediación: revisión manual + enriquecimiento de specs + re-evaluación con comparador research workstream.
- **Gate de cutover**: ningún SKU `blocked` puede pasar a `live` sin remediación o decisión explícita de Gerente.

### 14.5 FX as-of stamping

- Cada batch importado se sella con FX vigente al día del export del Excel.
- Costes y precios pre-existentes migrados marcados `fx_inferred = true`.
- Disclaimers en UI: "Coste migrado desde Excel; FX inferido."

### 14.6 Almacenamiento de imágenes — REQUISITO EXPLÍCITO DEL CLIENTE

**Origen del requisito**: pedido directo del cliente (sesión 2026-05-06): *"las imágenes que se guarden en el sistema sean en un bucket en Supabase"*. Refuerza ADR-033 y sube la decisión técnica a **regla de negocio no negociable**.

#### 14.6.1 Reglas duras

- **FR-IMG-01**: toda imagen de producto que ingrese al sistema (PIM, importer, alta manual, comparador, etc.) **DEBE** almacenarse en **Supabase Storage** bajo el bucket `product-images`. No se acepta hot-link a URLs externas (PIM España, Amazon CDN, fabricantes, etc.) en el campo operativo.
- **FR-IMG-02**: las imágenes externas detectadas en el ingreso de datos pasan por un proceso de **mirror obligatorio** (descarga + re-upload a `product-images`); el campo `image_url` del producto apunta siempre al bucket interno.
- **FR-IMG-03**: en imports y alta manual, si una imagen no puede mirrorearse (404, derechos, formato no soportado), el SKU se marca `image_status = missing` y queda excluido de exports/connectors hasta resolución.
- **BR-IMG-01**: ningún registro de producto puede pasar a `approved` sin tener al menos una imagen en `product-images` (se valida al pre-aprobar).
- **BR-IMG-02**: las URLs externas históricas (`image_url_pim`) se preservan en un campo `image_origin_url` para auditoría, pero no se usan como fuente operativa.

#### 14.6.2 Estructura del bucket `product-images`

Convención de paths:
```
product-images/
  ├── master/                    # imágenes oficiales del PIM España (mirror)
  │     └── {sku}/
  │           ├── primary.{ext}
  │           ├── alt-1.{ext}
  │           └── alt-N.{ext}
  ├── competitor/                # imágenes capturadas por el comparador
  │     └── {sku}/{listing_id}/{idx}.{ext}
  ├── uploads/                   # imágenes subidas manualmente desde la app
  │     └── {sku}/{user_id}/{timestamp}.{ext}
  └── thumbnails/                # versiones generadas (optimizadas, WebP)
        └── {sku}/{size}/...
```

#### 14.6.3 Políticas y acceso

- Bucket **privado por defecto**; acceso vía **signed URLs** generadas por el backend FastAPI con TTL configurable (default 24 h para UI interna, TTL más corto para exports a connectors).
- **RLS policies** sobre `storage.objects`:
  - Comercial: read+write sobre `master/` y `uploads/`; read-only sobre `competitor/` y `thumbnails/`.
  - Gerente Comercial: read en todo.
  - TI Integración: read+write en todo + delete bajo audit.
- **Tamaño máximo por imagen**: 10 MB (validación pre-upload).
- **Formatos aceptados**: JPEG, PNG, WebP, AVIF. SVG sólo desde fuentes confiables (master).
- **Generación de thumbnails**: pipeline async (Celery worker) genera variantes 256/512/1024 px en WebP al subir.
- **Limpieza**: imágenes de `competitor/` con TTL configurable (default 90 días post-decisión humana); de `uploads/` retenidas 1 año; de `master/` permanentes hasta unlink del SKU.

#### 14.6.4 Migración (S1)

- Probe de los 224 `image_url_pim` del PIM España.
- Mirror automático al bucket `product-images/master/{sku}/primary.{ext}`.
- Reporte de fallos (404, sin permisos, formato no soportado) entregado al Champion del Cambio para resolución.
- Acuerdo de derechos de imagen entre MT España ↔ MT ME documentado (responsabilidad legal de MT, no técnica).

#### 14.6.5 Casos relacionados

- **Fichas técnicas PDF**: bucket separado `product-datasheets` (FR-DOC-01).
- **Exports e imports**: bucket separado `import-batches` y `exports` (no mezclar con imágenes operativas).
- **Imágenes del comparador** (research workstream): bucket separado o subcarpeta `competitor/` dentro de `product-images` para no contaminar el master.

---

## 15. Operación y handoff

### 15.1 People readiness

- **Champion del Cambio**: nombrado antes de S1, dedicación ≥ 30 % durante migración.
- **Backup Operator**: cross-trained antes del cutover; acceso operativo a la app y conocimiento documentado del Excel.
- **Capacitación**: ≥ 2 sesiones hands-on antes del parallel run + manual operativo en español (`docs/handbook-es.md`).
- **SLA aprobación Gerente Comercial**: < 24 h en horario laboral; delegación obligatoria si ausencia > 48 h; escalado automático en cambios FX urgentes.
- **Walkthroughs grabados** de las sheets críticas del Excel maestro, archivados como referencia tácita.

### 15.2 Cutover gate firmado

Criterios de salida del parallel run:
- 100 % catálogo migrado.
- 0 diff entre app y Excel durante X días consecutivos (X ≥ 5).
- Audit trail validado en muestra de Y aprobaciones (Y ≥ 50).
- Backup operator capacitado y operó al menos 1 import + 1 aprobación.
- Manual operativo en español aprobado.
- Firmado por: Gerente Comercial + TI + sponsor MT (Christian).

### 15.3 Parallel run ≥ 2 semanas

- Cada cambio de precio se realiza en ambos sistemas (app + Excel demo).
- Reporte automático de diff diario.
- Criterio de salida: 0 diff por X días consecutivos.

### 15.4 Rollback playbook

- **Excel restorable** durante 90 días post-cutover.
- **Last-known-good export** regenerado diariamente y archivado.
- **Playbook de publicación manual** documentado: si la plataforma cae el día del go-live de Amazon UAE / Noon UAE (Fase 3), procedimiento conocido para publicar precios desde el último export aprobado.

### 15.5 Documentación operativa

- `docs/handbook-es.md` — manual usuario.
- `docs/admin-handbook.md` — guía TI.
- `docs/excel-mapping.md` — mapping sheet-by-sheet.
- `docs/runbook-import.md` — runbook importers.
- `docs/runbook-cutover.md` — runbook cutover + rollback.
- `docs/sla-approval.md` — SLA aprobación Gerente.

---

## 16. Riesgos y mitigaciones

| ID | Riesgo | Severidad | Probabilidad | Owner | Mitigación |
|----|--------|-----------|--------------|-------|------------|
| R-01 | Dependencia del Excel maestro como única fuente Fase 1 | Alta | Alta | Champion | Importer estricto + preview de diff + bloqueo de campos editados manualmente en la app + freeze post-import |
| R-02 | Single-point-of-failure: 1 sólo Comercial operando | Alta | Media | Pablo / Gerente | Backup operator cross-trained + manual operativo + walkthroughs grabados |
| R-03 | FX strategy: tasa hardcodeada en VBA | Alta | Alta (en migración) | TI | Sistema `fx_rates` versionado + FX as-of stamping + UI registro de tasa + revisión semanal |
| R-04 | AR translation governance: nadie valida AR internamente | Media | Media | Gerente | `translation_status` por idioma + AR no obligatorio en MVP + plan de validación externa para Fase 3 |
| R-05 | Stack TBD: TI MT puede rechazar el propuesto | Alta | Media | TI MT / Pablo | Sprint 0 dedicado a firma stack; sección técnica modular para reescritura |
| R-06 | Comparador unreliable (15 % SKUs sin match) | Alta | Alta | R&D Champion | Workstream R&D paralelo con métricas medibles + diferimiento a Fase 1.5 si no llega a threshold |
| R-07 | mtme.ae parked con SSL expirado | Media | Cierta | Programa MT (no Fase 1) | Flag al programa; no bloquea Fase 1 (interna); gating Fase 3 |
| R-08 | Activación asincrónica de canales crea estados intermedios | Media | Alta | TI | Estados explícitos `inactive`/`pre_launch`/`pilot`/`live`/`paused`/`deprecated` + simulación what-if |
| R-09 | VAT UAE 2026 / e-invoicing puede cambiar requisitos durante desarrollo | Alta | Media | Gerente / Sponsor | Diseño audit-first; cualquier cambio normativo se traduce a más columnas, no a refactor |
| R-10 | Cambio operativo Comercial (Excel → app) | Alta | Alta | Champion | Paridad funcional con Excel en S1 + capacitación + parallel run ≥ 2 semanas |
| R-11 | Sourcing de datos competidores (legalidad UAE, CAPTCHA, IP bans) | Media | Alta | R&D Champion | Decisión sourcing firmada en S0 con presupuesto; alternativas: API pagada (Keepa, DataForSEO) vs partnership marketplace |
| R-12 | Calidad del archivo PIM real al recibirlo | Alta | Media | Pablo / Champion | Muestra revisada en S0; mapeo inicial; importer con preview y rechazo de filas inválidas |
| R-13 | Performance importer fuera de NFR | Media | Baja | TI | Tareas en cola (Celery + Redis) + benchmarks en S2 con archivo real (PIM completo 5086 filas) |
| R-14 | Gerente Comercial cuello de botella en aprobaciones | Media | Media | Gerente | Auto-approve por excepción + bulk review + SLA + delegación + escalado >48 h |

---

## 17. Decisiones tomadas y rechazadas

| Decisión adoptada | Alternativa rechazada | Por qué |
|-------------------|----------------------|---------|
| Build custom | Akeneo / Pimcore / Odoo / SAP B1 / NetSuite / Pricefx / Vendavo | Pricing multi-canal/esquema + workflow excepción + comparador integrado no encajan en suites genéricas; lock-in y costo total más alto |
| Single-tenant MT | Multi-tenant white-label BR | BR desarrolla para MT como cliente, no productiza |
| Aprobación por excepción | Aprobación obligatoria 2-step | Equipo de 3 personas, aprobar todo se vuelve teatro |
| Fase 1 dividida 1a + 1b | Fase 1 monolítica | Entrega valor mid-phase, reduce riesgo, gate explícito antes de 1b |
| Stack del master doc descartado (Shopify+Supabase+Make.com) | (era el default) | Decisión del cliente: redefinir stack |
| Excel `stock_dubai_v23` ≠ source operativa | Source única Fase 1 | Aclaración usuario: Excel = demo, source real = PIM file + cost files |
| Recomendación canal "óptimo" detrás de feature flag | Visible Fase 1 | No hay canales `live` en Fase 1 |
| Sistema de comparación = research workstream | Port directo de v5.1 matcher | v5.1 falla 15 % del catálogo |
| AED como moneda base default | EUR | Operación UAE; AED es moneda local |
| EN canónico NOT NULL | Multi-canónico | Single source of truth para matching y export |
| FX as-of inmutable | Recálculo de pasados | Auditabilidad VAT UAE 2026 |
| Sin RTL UI Fase 1 | RTL completa | AR es contenido para export externo, no UI interna |
| **Stack alineado con `hppt-iom` (Next.js 16 + FastAPI + Supabase + Celery + Hetzner + Caddy)** — ADRs 028-037 | Next.js full-stack + Auth.js + BullMQ + R2 + Vercel (propuesta v1.0/v1.1, ahora superseded) | Reuso de patrones BR; Python permite ecosistema IA para comparador; Supabase reduce piezas; Hetzner abarata costo |
| **Fuentes reales catálogo Fase 1: `PIM completo.xlsx` + `catalogo_mt_productos.xlsx` + `Copia de Compatibilidad de Materiales MT V4.xlsx` + fichas técnicas PDF + estándares** | Sólo Excel demo / PIM España API | Detalle en sección 14 |
| **Persistencia híbrida SQLAlchemy 2.0 async (core data) + supabase-py (Auth/Storage)** — ADR-045 | supabase-py puro (1:1 con hppt-iom) o SQLAlchemy puro (ignorar Supabase Auth/Storage) | Complejidad pricing engine + comparador + audit analytics justifica ORM tipado y joins; Auth/Storage se reusan 1:1 desde hppt-iom sin valor añadido en duplicar tooling. App conecta a Postgres con rol específico `mt_app` que respeta RLS. **Decisión preliminar — sujeta a firma TI MT en S0.** |
| **Schedules editables vía DatabaseScheduler (tabla `job_definitions` + UI admin `/admin/jobs`)** — ADR-046 | Celery beat estático en código (versionado solo via deploy) | Gerente Comercial puede ajustar horarios de digest/KPI/FX recalc sin abrir ticket a TI; audit trail automático via trigger; +1 contenedor (beat replicas=1) + 1 tabla. Librería `celery-sqlalchemy-scheduler` o scheduler custom de ~150 líneas — decisión final Sprint 0. **Decisión preliminar — sujeta a firma TI MT en S0.** |

---

## 18. Fuera de alcance Fase 1

- **Fase 2**: módulo de inventarios, costos operativos, facturación con e-invoicing UAE-compliant, conexión bidireccional PIM/ERP MT Valves España.
- **Fase 3**: storefront B2C UAE en vivo, conectores activos a Amazon UAE (FBA + FBM) y Noon UAE, mtme.ae operativa.
- **Fase 4**: portal B2B distribuidores GCC con listas de precio negociadas, descuentos por volumen, multi-divisa (KSA, KW, OM, BH, QA), módulo contratos.
- **Conectores en vivo** a marketplaces (sólo shadow publish a sandbox en Fase 1).
- **Agente de reabastecimiento autónomo** (Fase 2.5-3).
- **Scraping competitivo Amazon UAE en producción** (queda como prueba de concepto offline).
- **Embeddings semánticos llenados** (columnas reservadas, no llenadas Fase 1).
- **Match semántico SKU↔competidores con pgvector** en producción (Fase 1.5+).
- **Recomendador de canal/precio basado en histórico** (Fase 2.5+).
- **Anomaly detection en feeds proveedor** (Fase 2.5+).
- **WhatsApp Business / chatbot**.
- **Identidad digital corporativa mtme.ae** remediación (responsabilidad fuera del sistema; flag al programa).
- **Integraciones API con PIM/ERP MT Valves España** (Fase 2+).
- **Dashboard "margin defense" con alertas FX/freight/customs en tiempo real** (Fase 1 COULD; probablemente Fase 2).

---

## 19. Glosario

| Término | Definición |
|---------|------------|
| **PIM** | Product Information Management. |
| **MDM** | Master Data Management. |
| **SKU** | Stock Keeping Unit. |
| **G1 / G2** | Grupos de competidores whitelisted (G1 primario, G2 secundario). |
| **FBA** | Fulfilled by Amazon. |
| **FBM** | Fulfilled by Merchant. |
| **DN** | Diameter Nominal (válvulas). |
| **PN** | Pressure Nominal (válvulas). |
| **Esquema de venta** | Modo logístico/comercial: FBA, FBM, Direct B2C, Direct B2B, Marketplace listado. |
| **Canal** | Destino comercial: Amazon UAE, Noon UAE, B2C directo, B2B distribuidores. |
| **Tier** | Nivel de matching: T0 brand → T2 técnico → T3 funcional → T4 product_name → T5 fallback → NONE. |
| **canal_recomendado** | Sugerencia del motor entre canales `live`. Off por feature flag Fase 1. |
| **pvp_min** | Precio de venta al público mínimo permitido. |
| **breakdown** | Desglose contable de coste y precio. |
| **alerts** | Etiquetas críticas/warning del motor de pricing. |
| **tier_used** | Tier efectivamente aplicado para matching. |
| **FX as-of** | Tasa de cambio sellada al momento de aprobación de coste o precio. |
| **data_quality** | Flag por SKU: `complete` / `partial` / `blocked`. |
| **exception_rule** | Regla paramétrica que decide auto-approve vs pending_review. |
| **shadow publish** | Export a sandbox marketplace para validación de formato. |
| **last-known-good** | Último export aprobado y archivado, usado como red de seguridad. |
| **VAT UAE 2026** | Enmiendas a la VAT UAE efectivas 1-Ene-2026. |
| **FTA** | Federal Tax Authority (UAE). |
| **AED** | United Arab Emirates Dirham. |
| **GCC** | Gulf Cooperation Council. |
| **state machine (precios)** | `draft → auto_approved | pending_review → approved | rejected | revised → exported`. |
| **escalated** | Flag en propuesta `pending_review` que lleva > 48 h sin resolver. |
| **bulk review** | Aprobación de lote homogéneo con un único comentario justificativo. |
| **digest diario** | Resumen diario al Gerente con auto-aprobados + pendientes + escaladas. |

---

## 20. Cuestiones abiertas a S0

| ID | Cuestión | Owner | Resolución esperada |
|----|----------|-------|---------------------|
| Q-01 | Stack tecnológico — **propuesto: Next.js 16 + FastAPI + SQLAlchemy 2.0 async + supabase-py (Auth/Storage) + Supabase Postgres + Celery + DatabaseScheduler + Hetzner + Caddy alineado con `hppt-iom`** (ADRs 028-037 + ADR-045 + ADR-046) vs alternativas que TI MT prefiera. **Decisión preliminar tomada (ver §17); espera firma TI MT en S0**. | TI MT / Paula | Sprint 0 |
| Q-02 | Cloud y residencia de datos (AWS/Azure/GCP/on-prem; obligación residencia UAE) | TI MT / Pablo | Sprint 0 |
| Q-03 | Confirmación del archivo PIM real + archivos de costos al recibirse, mapeo inicial | Pablo / Champion | Sprint 0 |
| Q-04 | Threshold X % delta margen para auto-approve vs pending_review | Gerente Comercial | Sprint 0 |
| Q-05 | TI Integración: FTE dedicado / role-share TI MT España / vendor externo. RACI firmado | Sponsor MT | Sprint 0 |
| Q-06 | mtme.ae remediación (parked, SSL expirado) — gating Fase 3, no Fase 1 | Programa MT | Sprint 0 (flag) |
| Q-07 | Dataset etiquetado del comparador: ≥ 50 pares; quién etiqueta + plazo | R&D Champion | S0 - S2 |
| Q-08 | Fuente de datos competidores: scraping vs API pagada (Keepa, DataForSEO) vs partnership marketplace + presupuesto | R&D Champion | Sprint 0 |
| Q-09 | Acuerdo de derechos de imagen MT España ↔ MT ME (mirror a Supabase Storage `product-images`) | Sponsor MT / legal | Sprint 0 - 1 |
| Q-10 | Decisión port-vs-rewrite del motor v5.1 (basada en pseudocódigo extraído) | TI MT + Pablo | Sprint 0 |
| Q-11 | Definición de "óptimo" para recomendador de canal (margen vs ROI vs rotación) | Gerente | Sprint 4 (gating Fase 3) |
| Q-12 | Ventanas de mantenimiento + horario soporte | TI / Gerente | Sprint 7 |
| Q-13 | Política de retención `audit_events` (default 7 años, alineado VAT UAE) | Sponsor / legal | Sprint 0 |
| Q-14 | Idioma del Sentry / observabilidad (interno equipo) | TI | Sprint 0 |
| Q-15 | Threshold de calibración del comparador (auto-match vs revisión humana) | R&D Champion | S2 con primera curva |
| Q-16 | Formato exacto del export por canal (Amazon UAE Seller Central, Noon UAE, Shopify-ready, B2B) | TI / Comercial | Sprint 6 |
| Q-17 | Política de delegación del Gerente: a quién escala >48 h | Gerente | Sprint 5 |
| Q-18 | ¿AR sólo en datos o eventualmente UI? Si futuro RTL UI → reservar i18n hooks | Gerente / Programa | Sprint 0 (anotado) |

---

## 21. Asunciones explícitas

(Declaradas para resolver ambigüedades del brief sin bloquear; revisar en S0.)

| ID | Asunción |
|----|----------|
| A-01 | Equipo de desarrollo TI MT acepta TypeScript / Node.js como stack principal salvo veto en S0. |
| A-02 | Cloud preferente con presencia en UAE (AWS me-central-1 / Azure UAE Central) salvo política contraria. |
| A-03 | El archivo PIM real entregado en S0 contiene como mínimo: SKU, name_en, family, dn, pn, type, material, image_url. Si no, S1 incorpora enriquecimiento manual. |
| A-04 | El Gerente Comercial dispone de ≥ 30 min/día en horario laboral para revisar la cola de aprobación. |
| A-05 | El threshold inicial de auto-approve es 5 % (delta margen); ajustable por Gerente sin ticket. |
| A-06 | La FX EUR→AED se actualiza manualmente por TI con fuente designada (default: openexchangerates.org u oficial UAE Central Bank) hasta que se firme un proveedor automatizado. |
| A-07 | La validación humana asistida del comparador es Fase 1.5+ por defecto; se acelera sólo si R&D entrega antes de S6. |
| A-08 | Imágenes externas tienen derechos de uso de MT España hacia MT ME; el acuerdo legal lo formaliza el sponsor MT. |
| A-09 | El catálogo no superará 1.000 SKUs en Fase 1 operativa real (224 + crecimiento moderado); el sizing de DB/cola se calibra a 50 k SKUs como horizonte arquitectónico, no operativo Fase 1. |
| A-10 | La regla dura "no aprobado no integra" se enforced a nivel DB (CHECK + filtros) y runtime (connector). Cualquier excepción debe pasar por feature flag explícito y registrarse en `audit_events`. |
| A-11 | Sentry y logs estructurados van a infraestructura controlada por MT (no Sentry SaaS público) si la política de residencia lo exige; alternativa: GlitchTip self-hosted. |

---

## 22. Apéndice — Trazabilidad de inputs

| Sección PRD | Input principal |
|-------------|-----------------|
| 1, 2, 3 | brief §Resumen, §Problema, §Criterios |
| 4 | brief §A quién sirve + distillate §Roles + §Personas |
| 5 | distillate §Modelo de datos núcleo + brief §Solución |
| 6, 7 | brief §Alcance + distillate §Workflow + stage2 §Insights motor v5.1 |
| 8 | brief §Investigación crítica + distillate §Sistema de comparación |
| 9 | brief §Riesgos + §Cutover + distillate §Stack |
| 10 | distillate §Modelo de datos + stage2 §Schema Supabase propuesto |
| 11 | derivado del modelo de datos + RBAC distillate |
| 12 | brief §A quién sirve + journey synthesis |
| 13 | brief §Plan + distillate §Plan |
| 14 | brief §Migración + distillate §Migración |
| 15 | brief §Personas + §Cutover + distillate §Cutover |
| 16 | brief §Riesgos + distillate §Cuestiones abiertas |
| 17 | distillate §Decisiones |
| 18 | brief §Fuera Fase 1 + distillate §Visión Fase 2-4 |
| 19 | brief + distillate + stage2 (consolidado) |
| 20 | distillate §Cuestiones abiertas + gaps detectados durante PRD |

---

**Fin del PRD — Fase 1 (1a + 1b)**

Próximos pasos:
1. Sprint 0 (1 semana) — gate de arranque (sec. 13.1).
2. Resolución de Q-01 a Q-18 antes de S1.
3. Firma del PRD por Sponsor MT (Christian) + Validador Técnico (Paula).
