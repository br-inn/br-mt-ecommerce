---
tags: [design, pricing-desk, lineage, freshness, api]
created: 2026-05-30
status: approved
audience: claude-code, backend
target_repo: br-mt-ecommerce
component: mt-pricing-backend
related: ["[[04-api-spec]]", "[[02-target-architecture]]", "2026-05-30-pricing-provenance-audit-f1-design"]
---

# Diseño — F4: Lineage + Frescura + Salud de fuentes (API)

## 1. Contexto y objetivo
F1 dejó la **provenance** (columnas `source_op`/`observed_at`/`valid_until`, `source_observations`, `source_health`, `audit_events`). F4 la **expone** vía endpoints de lectura (Pilar C "trazabilidad inline" del doc 02 y los endpoints del doc 04), para que cada cifra del Pricing Desk responda "¿de dónde vengo?" y se vea la frescura. **Solo backend** este ciclo; los drawers de frontend son un ciclo aparte. F4 **se apoya en F1** (rama stacked) y **no añade migración** (solo lectura).

## 2. Alcance
**Dentro (5 endpoints GET, prefix `/pricing/{channel_code}`, permiso `prices:read`):**
1. `GET /sources/health`
2. `GET /freshness`
3. `GET /lineage/{sku}/{field}` (`field ∈ cost|ceiling`)
4. `GET /parameters/{key}/audit`
5. `GET /products/{sku}/card`

**Fuera:** drawers de frontend (ciclo UI aparte); jobs que *pueblan* `source_health`/observations (F2/F3/F6); escritura (F1 ya cablea las mutaciones).

## 3. Arquitectura
- **Servicio de lectura nuevo** `app/services/pricing/provenance_query.py` — funciones puras de ensamblado (sin HTTP): `sources_health(session)`, `freshness(session, channel_id, selling_model)`, `lineage(session, channel_id, sku, field, selling_model)`, `parameter_audit(session, channel_id, key)`, `product_card(session, channel_id, sku)`. Cada una devuelve un dataclass/dict; los handlers solo validan + serializan.
- **Schemas** en `app/schemas/provenance_query.py` (Pydantic responses).
- **Handlers** en `app/api/routes/channel_pricing.py` (mismo prefix; thin).
- Reutiliza: `SourceHealth`/`SourceObservation` (F1), `AuditRepository.list_for_entity`, `ParameterLoader`+`PricingEngine` (para lineage: explota el `CostBreakdown`), `marketplace_listing`/`prices`/`price_approval_events` (ficha).

## 4. Endpoints (contrato)

### 4.1 `GET /sources/health`
Lee `source_health` (todas las filas). `is_healthy` **derivado en la API**: `last_sync_success_at IS NOT NULL AND (now - last_sync_success_at) < freshness_sla_minutes`. Respuesta:
```jsonc
{ "sources": [ {"source_op","last_sync_attempt_at","last_sync_success_at","last_error",
                "freshness_sla_minutes","age_minutes"|null,"is_healthy":bool} ],
  "blocking": ["master_canal", ...] }   // fuentes CRÍTICAS no sanas (FX, master_canal, vendor_price_list)
```
Hoy `last_sync_success_at` es NULL en todas (sin syncs aún) → `is_healthy=false`, `age_minutes=null`. Es el estado honesto; los jobs de F2/F3/F6 lo poblarán.

### 4.2 `GET /freshness?selling_model=`
Frescura **por parámetro** (filas de las 5 tablas de config del canal: `observed_at`/`valid_until`/`source_op`) y, si aplica, por SKU (desde `source_observations`). Cada item: `{scope:"param"|"sku", key, source_op, observed_at, valid_until, is_stale}`. `is_stale = valid_until IS NOT NULL AND now > valid_until` (o `observed_at IS NULL`).

### 4.3 `GET /lineage/{sku}/{field}` (`field=cost|ceiling`)
Calcula el SKU con `ParameterLoader`+`PricingEngine` (mismo cómputo que `/product/{sku}`), y explota el `CostBreakdown` (las 5 capas: `net_eur`, `fx_applied`, `aed_before_freight`, `freight_aed`, `landed_aed`, `labeling_aed`, `channel_logistics_aed`, `cost_op_aed`; o el techo) en componentes con su **source_ref** (de las columnas `source_op`/`source_ref` de las tablas de config + observaciones de `pe_eur`/`catalog_pvp_eur`). Respuesta: `{sku, field, total_aed, layers:[{layer,label,amount_aed,components:[{key,value,source_op,source_ref,observed_at,is_stale}]}]}`. 404 si el SKU no tiene logistics/precio.

### 4.4 `GET /parameters/{key}/audit`
`key` identifica el parámetro (`route`, `fees`, o `margin:<family_id>`, etc.). Resuelve el `entity_id` (id de la fila de config) y devuelve `AuditRepository.list_for_entity(entity_type, entity_id)` mapeado: `[{actor_id, action, before, after, reason, event_at}]`, orden desc.

### 4.5 `GET /products/{sku}/card`
Ensambla:
- **master**: `products` (sku, pe_eur, catalog_pvp_eur, units_per_box, weight, hs_code, family) + `updated_at` / última observación.
- **price_history**: `source_observations` del sku para `pe_eur`/`catalog_pvp_eur` (orden desc, límite 20).
- **listing**: `marketplace_listing` del sku+canal si existe (estado, precio publicado), o null.
- **proposals**: `prices` del sku+canal (status, amount, created_at) + transiciones de `price_approval_events` (limit 20).
Campos ausentes → null/[]; nunca 500 por datos faltantes.

## 5. Errores y rendimiento
- 404 SKU/canal inexistente; campos opcionales ausentes → null/[] (sin 500).
- `CacheControlMiddleware` ya aplica `private, max-age=60` a GET 200 (no añadir headers).
- Lineage: 1 cálculo en memoria (barato); las consultas usan los índices de F1 (`idx_source_obs_lookup`).

## 6. Pruebas (integración, Postgres _149, rollback)
- `sources/health`: 14 filas, todas `is_healthy=false` (sin sync), `blocking` incluye las críticas.
- `freshness`: parámetro con `observed_at` reciente → `is_stale=false`; con `valid_until` pasado → `is_stale=true`.
- `lineage/{sku}/cost`: devuelve capas con `total_aed`>0 y `source_ref` por componente; 404 si SKU sin logistics.
- `parameters/{key}/audit`: tras una mutación (sembrar un audit_event) → lo lista.
- `products/{sku}/card`: master poblado; listing/proposals null/[] si no hay; no 500.
- Regresión: rutas existentes verdes; cobertura ≥70%.
- **OpenAPI**: F4 **añade endpoints** → regenerar spec de raíz + `lib/api/types.ts` (regla CI).

## 7. Reutilización vs nuevo
| Existe | Nuevo (F4) |
|---|---|
| `SourceHealth`/`SourceObservation`, `AuditRepository`, `ParameterLoader`+`PricingEngine`, `marketplace_listing`/`prices`/`price_approval_events` | `provenance_query.py` (servicio), `schemas/provenance_query.py`, 5 handlers GET, tests |

## 8. Decisiones
- `is_healthy` derivado en API (no almacenado) — coherente con F1.
- Fuentes "críticas" para `blocking`: `tesoreria_fx`, `master_canal`, `vendor_price_list` (configurable luego).
- `field` de lineage: `cost` y `ceiling` (B2C por defecto; `selling_model` query param).
- Ficha tolerante a datos ausentes (null/[]), nunca 500.

## 9. Decisiones abiertas (a resolver en el plan)
- `key` de `/parameters/{key}/audit`: formato exacto (`route`/`fees`/`margin:<family_id>`/`override:<sku>`) y cómo mapear a `entity_type`/`entity_id` de los `audit_events` que F1 emite.
- Columnas exactas de `marketplace_listing`/`prices`/`price_approval_events` (el plan las lee para la ficha).
