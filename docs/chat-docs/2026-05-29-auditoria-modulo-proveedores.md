# Auditoría transversal — Módulo de Proveedores

**Fecha:** 2026-05-29
**Rama:** `feat/pricing-desk-invoice-ingestion`
**Alcance:** Revisión transversal completa del módulo de proveedores (suppliers/proveedores):
backend, frontend, modelo de datos, interconexiones con Compras/Costos/Inventario/Finanzas,
i18n, tests. **Decisión tomada:** `vendor_id` debe unificarse con `suppliers.code` (mismo proveedor).

---

## 1. Resumen ejecutivo

El núcleo CRUD de proveedores (tabla `suppliers`, PK `code`) está **bien implementado y completo**
en backend y en la UI canónica `/proveedores`. El problema de fondo es de **integración**: el módulo
de Compras (y Finanzas) usa un identificador de proveedor en texto libre (`vendor_id`) **sin FK** al
maestro `suppliers`. El propio código ya los trata como equivalentes, y no existe un maestro de
"vendors" separado → la separación es deuda técnica, no diseño. Hay además UI duplicada huérfana
(`/suppliers`, inglés) que retiene todos los tests, y varias funciones a medias.

---

## 2. Estado por capa (núcleo CRUD)

### Backend — ✅ completo (~85/100)

| Capa | Archivo | Estado |
|------|---------|--------|
| Modelo | `app/db/models/supplier.py` | PK `code`, FK `contract_currency`→currencies (RESTRICT), soft-delete `active`, índices parciales, trigger `updated_at` |
| Schemas | `app/schemas/supplier.py` | Create/Update/Patch/Response; regex `^[A-Z0-9][A-Z0-9_\-]{1,63}$`, EmailStr, lead_time 0–3650; todos los campos del modelo cubiertos |
| Repo | `app/repositories/supplier.py` | CRUD + paginación cursor por `code`, filtros active/currency/search |
| Service | `app/services/suppliers/supplier_service.py` | CRUD + audit before/after/diff |
| Rutas | `app/api/routes/suppliers.py` | GET list/detail, POST, PUT, PATCH, DELETE→405 (VAT) |
| Migración tabla | `alembic/versions/20260507_004_currencies_suppliers_schemes.py` | Columnas, FK, índices, trigger, RLS (read-all / write comercial+) |
| Migración permisos | `alembic/versions/20260507_011_suppliers_permissions.py` | `suppliers:read` → comercial, gerente_comercial, ti_integracion, admin; `suppliers:write` → ti_integracion, admin |
| Registro router | `app/api/routes/__init__.py:113` | ✅ incluido |

### Frontend `/proveedores` (ES) — ✅ completo (UI viva, en sidebar `sidebar.tsx:79`)

- Páginas: `page.tsx` (lista), `nuevo/`, `[code]/` (detalle, tabs Datos/Costos/Auditoría), `[code]/editar/`.
- Componentes: form (crear/editar con validación + mapeo de errores 409/Pydantic), tabla (cursor infinite scroll), toolbar (search + currency + active), filtros (estado en URL), menú de acciones (ver/editar/archivar/activar con diálogo de confirmación).
- API client `lib/api/endpoints/suppliers.ts` + hooks `lib/hooks/suppliers/use-suppliers.ts`: list/get/create/patch/setActive — **todos cableados**.
- i18n: claves `proveedores.*` y `suppliers.form.validation.*` **completas en ES/EN/AR**.

---

## 3. Interconexión con el sistema

### (A) Enlazadas por FK a `suppliers.code` — integridad referencial real

| Tabla | Columna | Tipo | OnDelete | Ubicación |
|-------|---------|------|----------|-----------|
| `costs` | `supplier_code` | TEXT | SET NULL | `cost.py:82` |
| `purchase_orders` | `supplier_code` | String(64) | RESTRICT | `inventory.py:59` |

UI: selector de proveedor cableado en `po-form.tsx` y en costos; tab "Costos asociados" en el detalle del proveedor.

### (B) `supplier_code` String **sin FK** — snapshot histórico (aceptable, sin integridad)

| Tabla | Columna | Ubicación |
|-------|---------|-----------|
| `cost_lots` | `supplier_code` String(64) | `inventory.py:238` |
| `inventory_positions` | `supplier_code` String(64) | `inventory.py:318` |

### (C) `vendor_id` texto libre **sin FK** — 🔴 desconectado del maestro

| Tabla | Módulo | Tipo | Ancho vs `code`(64) | Ubicación |
|-------|--------|------|---------------------|-----------|
| `vendor_product_conditions` (PIR) | Compras | String(64) | 64 ✓ | `procurement.py:181` |
| `vendor_invoices` | Compras | Text | 128 ⚠️ overflow | `procurement.py:233` |
| `source_list` | Compras | Text | 128 ⚠️ overflow | `procurement.py:314` |
| `rfq_vendor_responses` | Compras | Text | 128 ⚠️ overflow | `procurement.py:429` |
| `vendor_open_items` | **Finanzas (AP aging)** | Text | sin límite ⚠️ | `finance.py:353` |

**Mapeo implícito existente:** `purchase_order.py:104` consulta `VendorProductCondition.vendor_id == PO.supplier_code`
→ el sistema ya asume que `vendor_id` y `supplier_code` son el mismo proveedor.

**Maestro único confirmado:** no existe tabla `vendors`; `suppliers` es el único maestro.

`purchase_requisitions.suggested_vendor_id` es `UUID` (distinto concepto) → **no se toca**.

---

## 4. Hallazgos / funciones incompletas

| # | Severidad | Hallazgo | Ubicación |
|---|-----------|----------|-----------|
| 1 | 🔴 Alta | 5 tablas con `vendor_id` sin FK a `suppliers.code` (Compras + Finanzas) | ver §3C |
| 2 | 🟠 Media | UI de condiciones-proveedor captura `vendor_id` como texto libre, no selector | `admin/condiciones-proveedor/page.tsx:117` |
| 3 | 🟠 Media | Tests frontend (e2e `05-suppliers-crud`, unit `suppliers-*`) apuntan a la UI **huérfana `/suppliers`**, no a `/proveedores`. La UI viva no tiene tests | `tests/e2e/05-suppliers-crud.spec.ts`, `tests/unit/suppliers/*` |
| 4 | 🟠 Media | Árbol `/suppliers` (inglés) es duplicado huérfano (no en sidebar); eliminar requiere migrar tests primero | `app/(app)/suppliers/**` |
| 5 | 🟡 Baja | Tab "Auditoría" del detalle es placeholder ("Pendiente Sprint 2") pese a que los eventos sí se graban server-side | `proveedor-detail.tsx:139-155` |
| 6 | 🟡 Baja | `soft_delete_supplier()` es código muerto (ningún endpoint lo llama) | `supplier_service.py:212` |
| 7 | 🟡 Baja | Cobertura de tests backend 9/18: faltan validación email, filtros `q`/`active`, FK currency en PUT, rechazo PATCH vacío, aserciones de audit | `tests/api/test_suppliers_crud.py` |
| 8 | 🟡 Baja | `cost_lots` / `inventory_positions` con `supplier_code` sin FK | `inventory.py:238,318` |
| 9 | 🟡 Baja | Width mismatch: schemas `vendor_id` permiten 128 chars vs `code` 64 | `schemas/procurement.py:181,255,339` |

---

## 5. Roadmap de remediación propuesto

### Fase 1 — Limpieza (bajo riesgo)
- Eliminar árbol huérfano `/suppliers` tras migrar e2e/unit tests a `/proveedores`.
- Eliminar `soft_delete_supplier()` muerto (o cablearlo si se prefiere).
- Implementar tab "Auditoría" leyendo `audit_events` (read side ya existe en backend).
- Completar tests backend (los ~9 escenarios faltantes).

### Fase 2 — Unificación `vendor_id` → `suppliers.code` (alto impacto)
1. **Backfill/validación de datos:** verificar que todo `vendor_id` existente exista en `suppliers.code`;
   crear faltantes o archivar huérfanos. (Truncar/reconciliar valores > 64 chars.)
2. **Migración Alembic:** reducir ancho a 64, normalizar a uppercase, añadir FK a `suppliers.code`
   en las 5 tablas (`vendor_product_conditions`, `vendor_invoices`, `source_list`,
   `rfq_vendor_responses`, `vendor_open_items`). Definir `ondelete` (RESTRICT recomendado).
   Aplicar split de migraciones: Supabase para RLS si aplica, luego Alembic.
3. **Schemas backend:** alinear `vendor_id` a `SupplierCodeStr` (max 64, regex, uppercase).
4. **Validación API:** rechazar `vendor_id` inexistente en `suppliers` (vía FK + manejo IntegrityError UX-friendly).
5. **UI:** reemplazar el input libre de `vendor_id` en condiciones-proveedor por selector de proveedor
   (reusar `useSuppliers`); aplicar el mismo selector en facturas/RFQ si capturan vendor.
6. **Regenerar OpenAPI** (`export_openapi`) por cambios en `schemas/procurement.py` / rutas.

### Fase 3 — Endurecer integridad (opcional)
- Evaluar FK en `cost_lots` / `inventory_positions` o validación a nivel de servicio MAP.

---

## 6. Pendiente de verificar (no cubierto en esta auditoría)
- Ejecución real de `pytest` y vitest en verde.
- Estado de datos en el entorno dev (cuántos `vendor_id` huérfanos existen) — determina el esfuerzo de backfill.
