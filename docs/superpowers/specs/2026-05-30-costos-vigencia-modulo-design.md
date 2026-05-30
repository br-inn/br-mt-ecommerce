# Diseño — Módulo de Costos por esquema con vigencia (rangos + auto-encadenado)

**Fecha:** 2026-05-30
**Estado:** Diseño aprobado (pendiente revisión final del spec)
**Autor:** psierra + Claude

---

## 1. Contexto y problema

Hoy los costes por esquema de venta viven en la tabla `costs` con temporalidad
**parcial**: `effective_at` (timestamp) + versionado por `status` (active/superseded)
+ `version`, con FX as-of. La gestión está dispersa (dashboard `/costos` read-only,
editor `/catalogo/[sku]/costos`, mini-lista en el detalle del proveedor) y **no modela
vigencia como rango**: no se puede consultar "el coste vigente a una fecha", ni programar
cambios futuros, ni ver la línea de tiempo de vigencias.

**Objetivo:** elevar los costes por esquema a un **módulo de primera clase** con
**vigencia por rangos de fechas** (`valid_from`/`valid_to`) y transición **auto-encadenada**
(timeline continuo, sin solapes ni huecos), reutilizando el sistema de diseño existente.

### Decisiones tomadas (brainstorming)
- **Vigencia = rango de validez** (`valid_from`–`valid_to`); permite consultar a cualquier fecha (pasada/futura) y da costes futuros "gratis".
- **Transición = auto-encadenado, timeline continuo**: cargar un coste "desde D" cierra el anterior en D−1; a cualquier fecha hay **exactamente un** coste vigente.
- **Alcance = A+B**: núcleo de vigencia (modelo + API) **y** módulo/UI dedicado. Se difieren C (integración avanzada del pricing / histórico extendido) y D (workflow de aprobación / notificaciones).
- **Modelo = Enfoque 1**: extender `costs` con `valid_from`/`valid_to` + constraint de no-solape; conservar la tabla.
- **Auto-encadenado en el service** (`cost_service`), con la **constraint de exclusión** como red de seguridad a nivel BD. (Refinamiento sobre la idea inicial de trigger, por testeabilidad.)

---

## 2. Lo que ya existe (no reinventar)

- **Backend:** `app/db/models/cost.py` (versionado + FX as-of trigger), `app/api/routes/costs.py`
  (POST/PUT/GET/PATCH/DELETE + `/products/{sku}/costs` + `/costs/missing`),
  `app/services/costs/cost_service.py`, `app/services/importer_costs/*` (preview/apply Excel),
  `app/db/models/cost_scheme.py` + `routes/schemes.py` (catálogo FBA/FBM/DIRECT_B2C/DIRECT_B2B/MARKETPLACE
  con `cost_components_template`), triggers `costs_stamp_fx` + `costs_compute_landed_aed`
  (migración `alembic/versions/20260507_018_costs_engine.py`).
- **Frontend:** `app/(app)/costos/*` (dashboard cobertura read-only),
  `app/(app)/catalogo/[sku]/costos/*` (editor por SKU: CostTable, CostFormSheet,
  CostBreakdownEditor, historial), `lib/hooks/costs/use-costs.ts`,
  `lib/api/endpoints/costs.ts`, mini-lista en `proveedores/_components/proveedor-detail.tsx`.
- **Sistema de diseño:** Shadcn new-york + primitivos/tokens MT (`MtButton`, `SectionCard`,
  `Pill`, `Badge`, `MtSkeleton/Empty/Error`), `DataTable`, `Tabs`, `Sheet`.

---

## 3. Modelo de datos (Enfoque 1)

Cambios en la tabla `costs`:

| Columna | Cambio |
|---------|--------|
| `valid_from DATE NOT NULL` | Inicio de vigencia (granularidad **día**). Backfill = `effective_at::date`. |
| `valid_to DATE NULL` | Fin de vigencia **inclusive**; `NULL` = abierto (coste vigente actual). |
| `effective_at` (timestamp) | **Se dropea** la columna; el modelo expone `effective_at` como **hybrid** alias de `valid_from` (back-compat). |
| `status` (active/superseded) | **Se dropea** (+ su check). "Estado" pasa a derivarse por fecha (Vigente/Programado/Caducado). Hybrid `status` en el modelo para legacy. |
| `version` | Se conserva (auditoría/historial). |

**Auto-encadenado (service):** al insertar un coste para `(sku, scheme_code, supplier_code)`
con `valid_from = D`, `cost_service.create_cost` cierra el rango abierto anterior poniéndole
`valid_to = D − 1` y la nueva fila queda con `valid_to = NULL`. Un coste con `D` futuro no
afecta la consulta "a hoy" (el anterior sigue conteniendo hoy hasta D−1).

**No-solape (invariante a nivel BD):**
```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE costs ADD CONSTRAINT ex_costs_no_overlap
  EXCLUDE USING gist (
    sku WITH =,
    scheme_code WITH =,
    coalesce(supplier_code,'') WITH =,
    daterange(valid_from, valid_to, '[]') WITH &&
  );
```
Reemplaza el índice único parcial `idx_costs_active_unique_lookup` (que era `status='active'`).
`daterange(..,'[]')` con `valid_to = NULL` → rango no acotado por arriba.

**FX as-of:** el trigger `costs_stamp_fx` pasa a resolver el tipo de cambio en `valid_from`
(antes `effective_at`). `costs_compute_landed_aed` no cambia (keyed en breakdown/fx_rate_id).

**Consultas clave:**
- *Coste vigente a fecha X*: `WHERE sku=:sku AND scheme_code=:s AND coalesce(supplier_code,'')=:sup AND :X BETWEEN valid_from AND coalesce(valid_to, DATE 'infinity')`.
- *Vigente hoy*: lo anterior con `:X = current_date` (sustituye a `status='active'`).

---

## 4. API / Backend

**Ciclo de vida** (reemplaza el "supersede"):
- **Cambio de coste** = `POST /costs` con `valid_from`. El service auto-encadena; devuelve `{cost, warnings}`.
- **Corrección en sitio** = `PATCH /costs/{id}` (arreglar desglose o mover `valid_from`); muta la fila, re-estampa FX/`landed_aed`; la exclusión rechaza solapes.
- **Descatalogar** = `POST /costs/{id}/close` con `valid_to`; cierra el rango abierto sin sucesor.

**Endpoints:**

| Método | Ruta | Propósito |
|--------|------|-----------|
| `GET` | `/costs/as-of?sku=&scheme_code=&supplier_code=&date=` | **Nuevo.** Coste vigente a una fecha (pasada/futura). |
| `GET` | `/costs?sku=&scheme=&supplier=&valid_on=&include_history=&order=valid_from` | Listado global del módulo + datos de timeline (historial ordenado). |
| `GET` | `/products/{sku}/costs?as_of=` | Costes por esquema vigentes a fecha (default hoy). Sustituye "active". |
| `GET` | `/costs/missing?scheme_code=&as_of=` | Cobertura por esquema a una fecha. |
| `POST` | `/costs` | Cambia: recibe `valid_from`; auto-encadenado. |
| `PATCH` | `/costs/{id}` | Corrección en sitio (deja de ser supersede). |
| `POST` | `/costs/{id}/close` | **Nuevo.** Descatalogar. |
| `DELETE` | `/costs/{id}` | Se conserva (admin/tests). |

**Importador:** se añade columna `valid_from` por fila; `apply` usa el auto-encadenado del
service y admite filas **futuras**; el `differ` compara contra el coste vigente a ese `valid_from`.

**Adaptación obligatoria de consumidores (parte de A):** todo lo que filtra `status='active'`
pasa a "coste vigente hoy" (as-of today): motor de **pricing** (repo/service), `cost_service`,
y los lookups de los editores. Sin esto el pricing dejaría de encontrar costes al quitar `status`.

**OpenAPI:** regenerar `_bmad-output/planning-artifacts/mt-api-contract-openapi.json` y
commitearlo en el mismo PR (regla CI de drift).

---

## 5. Módulo / UI (`/costos`), sistema de diseño actual

**Arquitectura de información** — `/costos` con `Tabs`:
- **Resumen** → dashboard de cobertura por esquema existente (reusado).
- **Costes** → listado global filtrable (todos los SKU).
- **Importar** → flujo existente + columna `valid_from`.
- **Detalle de clave** (SKU × esquema × proveedor) → **timeline de vigencias** (reusa/eleva el
  editor de `/catalogo/[sku]/costos`; accesible desde catálogo y desde el tab del proveedor).

**Componentes (reusar vs nuevo):**

| Componente | Origen |
|------------|--------|
| `CostosToolbar` (filtros URL: SKU, esquema, proveedor, vigente-a-fecha, toggle historial) | patrón `proveedores-toolbar` |
| `CostosTable` (`DataTable`: sku, esquema, proveedor, `valid_from`, `valid_to`, `landed_aed`, badge estado) | `DataTable` |
| `CostTimeline` (**nuevo**, sin librería de charts) | `SectionCard` + `Badge` + tokens MT |
| `CostFormSheet` + `CostBreakdownEditor` (extender: date picker `valid_from`, modos *nuevo/corrección*, botón *descatalogar*) | existentes |
| Hooks `useCostAsOf`, timeline vía `useCosts(include_history)` | sobre `use-costs.ts` |

**Timeline (mock ASCII, mismo look del sistema):**
```
FBA · MT_SPAIN_SA
 ├─ 01 ene → 31 may 2026   1,240.00 AED   [Caducado]
 ├─ 01 jun → (abierto)     1,310.00 AED   [Vigente]   ← hoy
 └─ 01 ago → (futuro)      1,290.00 AED   [Programado]
[+ Nuevo coste desde fecha]  [Corregir]  [Descatalogar]
```

**Badges derivados por fecha:** *Vigente* (hoy ∈ rango), *Programado* (`valid_from` futuro),
*Caducado* (`valid_to` < hoy).

**Convenciones (CLAUDE.md):** filtros en URL; `staleTime` 30s (listados) / 300s (esquemas);
`isLoading`/empty/error por sección. **RBAC:** `costs:read` ver, `costs:write` crear/corregir/
descatalogar/importar (`RbacGuard`).

El tab "Costos asociados" del **proveedor** pasa de mini-lista a rangos vigentes + link al módulo.

---

## 6. Migración (Alembic, `public.*`)

1. `CREATE EXTENSION IF NOT EXISTS btree_gist`.
2. Añadir `valid_from DATE`, `valid_to DATE NULL`.
3. **Backfill por clave** (sku, esquema, coalesce(supplier_code)): ordenar versiones por
   `effective_at`; `valid_from = effective_at::date`; `valid_to = (siguiente valid_from) − 1`;
   la última (hoy `active`) queda abierta (`NULL`). Tie-break por `version`/`created_at` si
   coincide `effective_at`. Luego `valid_from NOT NULL`.
4. Quitar `idx_costs_active_unique_lookup`; añadir la exclusión `ex_costs_no_overlap`.
5. Triggers: `costs_stamp_fx` ancla en `valid_from`; `costs_compute_landed_aed` sin cambios.
6. Dropear `status` (+ check) y `effective_at`; el modelo expone ambos como **hybrids**
   derivados. Conservar `version`.
7. `downgrade` reconstruye `status`/`effective_at` desde los rangos (reversible).

> Orden split: solo Alembic (`public.*`); no hay cambios de RLS (las columnas nuevas heredan
> la RLS de la tabla). Aplicar vía `./infra/scripts/migrate.sh`.

---

## 7. Testing (TDD — tests primero)

- **Migración/DB** (`tests/db/`, `tests/data/`): la exclusión rechaza solapes para la misma
  clave; backfill produce cadena contigua con última abierta; FX estampado en `valid_from`;
  `downgrade` reversible.
- **Service** (`tests/services/costs/`): auto-encadenado cierra el previo en D−1; coste futuro
  no afecta "a hoy"; `as-of` correcto (pasado/hoy/futuro); descatalogar; corrección in-situ
  re-estampa `landed`; solape → IntegrityError → 4xx.
- **API** (`tests/api/`): endpoints nuevos/cambiados (`as-of`, `close`, list `valid_on`/
  `include_history`, POST `valid_from`, PATCH) + RBAC + ProblemDetails.
- **Regresión pricing**: el motor encuentra el coste vigente vía `as-of(today)` tras quitar `status`.
- **Importador**: import con `valid_from` incl. filas futuras; differ vs coste-vigente-a-`valid_from`.
- **Frontend (vitest)**: `CostosTable`/`CostosToolbar`/`CostTimeline` (badges por fecha, filtros)
  y `CostFormSheet` (modos nuevo/corregir/descatalogar).

---

## 8. Secuencia de implementación (rollout)

1. **Backend modelo + migración** (columnas, backfill, exclusión, triggers) + tests DB.
2. **Service** (auto-encadenado, as-of, close, corrección) + tests service.
3. **Adaptar pricing/consumidores** a as-of(today) + regresión.
4. **API** (endpoints nuevos/cambiados) + tests API + **OpenAPI regen**.
5. **Importador** (columna `valid_from` + futuras) + tests.
6. **Frontend módulo** (`/costos` tabs, CostosTable/Toolbar, CostTimeline, CostFormSheet
   extendido) + vitest.
7. Tab del proveedor → rangos vigentes + link.

El cambio de modelo + adaptación de pricing es lo delicado; cada paso queda tras su suite.
Considerar feature flag para exponer el módulo UI nuevo.

---

## 9. Fuera de alcance (iteraciones futuras)

- **C** — integración avanzada del pricing (consumir coste vigente a la **fecha de cálculo**
  histórica, no solo hoy) + consultas históricas extendidas / impacto en márgenes.
- **D** — workflow de aprobación (estados pending/approved, sign-off de Finanzas) y
  notificaciones de cambios de coste.
- Campañas de ajuste masivo ("+10% a todos los FBA del proveedor X desde fecha").

---

## 10. Riesgos

- **Adaptación del pricing**: quitar `status='active'` toca el camino crítico de precios →
  cubrir con regresión antes de migrar.
- **Backfill**: claves con `effective_at` duplicado o datos inconsistentes → tie-break definido
  + validación post-migración (sin solapes, exactamente una fila abierta por clave).
- **`btree_gist`**: requiere la extensión; verificar permisos en la DB destino (cloud Supabase).
- **Blast radius**: `status`/`effective_at` aparecen en schemas, frontend `Cost` type, importer
  differ → inventariar todos los consumidores antes de dropear.
