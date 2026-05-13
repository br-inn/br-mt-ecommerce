---
stepsCompleted: [research, epics-stories]
inputDocuments:
  - technical-erp-master-data-mejores-practicas-industria-research-2026-05-13.md
  - technical-erp-inventario-mejores-practicas-research-2026-05-13.md
  - technical-erp-compras-mejores-practicas-research-2026-05-13.md
  - technical-erp-pricing-mejores-practicas-research-2026-05-13.md
  - technical-erp-ventas-mejores-practicas-research-2026-05-13.md
  - technical-erp-billing-mejores-practicas-research-2026-05-13.md
  - technical-erp-finanzas-mejores-practicas-research-2026-05-13.md
  - technical-ux-producto-erp-validacion-mejoras-sap-fiori-research-2026-05-13.md
generated: "2026-05-13T00:00:00.000Z"
project: "MT Middle East — ERP Best Practices Sprint Series (S13+)"
total_mejoras_investigadas: 186
---

# ERP Best Practices — Plan de Sprint S13+

**Fuente:** 8 archivos de investigación técnica · 186 mejoras identificadas
**Inspiración:** SAP S/4HANA · Oracle NetSuite · Microsoft Dynamics 365 · Odoo 18 · SAP Fiori · Akeneo PIM

## Resumen de mejoras por módulo

| Módulo | Mejoras | Epic |
|--------|---------|------|
| UX Producto (Fiori/Akeneo) | 10 | EP-ERP-01 |
| Inventario v2 (Movement Types, Trazabilidad) | 25 | EP-ERP-02 |
| Compras P2P (PR, Approval, PIR, 3-way match) | 23 | EP-ERP-03 |
| Ventas O2C (ATP, Credit, RMA, Delivery) | 21 | EP-ERP-04 |
| Billing & Facturación (Invoice, Dunning, e-Invoice) | 20 | EP-ERP-05 |
| Finanzas (GL, AP, CO, Close, Reporting) | 22 | EP-ERP-06 |
| **TOTAL** | **121 mejoras en estos 6 epics** | — |

> Las mejoras de Maestros de Datos (47) y Pricing (18) están en gran parte ya implementadas
> en EP-1A-* (PIM) y EP-1B-* (Pricing Engine). Se incluyen referencias cruzadas donde aplica.

---

## Epic EP-ERP-01 — UX Producto: SAP Fiori / Akeneo patterns

**Motivación:** La página de producto actual usa patrones genéricos. SAP Fiori, Akeneo y D365
definen patrones específicos para ERPs: Object Page con KVPs en el header, tabs por rol funcional
(Mercados, Unidades, Clasificación), y lifecycle status con semántica visual. Implementar estos
patrones mejora la usabilidad para el equipo comercial de MT.

**Stack:** Next.js 16 + React 19 + Tailwind v4 + Shadcn/ui new-york + FastAPI (endpoints mínimos)

### Resumen de stories EP-ERP-01

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-01-01 | LifecycleStatusBadge + Quick Facts header (UX-01, UX-02) | 5 | P0 | S13 |
| US-ERP-01-02 | Tab "Mercados" con product_releases + "Activar mercado" (UX-03, UX-10) | 8 | P0 | S13 |
| US-ERP-01-03 | Tab "Unidades" — base_uom + tabla conversiones (UX-04) | 5 | P1 | S13 |
| US-ERP-01-04 | GTIN en specs card + lifecycle chip en listado (UX-05, UX-07) | 3 | P1 | S13 |
| US-ERP-01-05 | Completeness ring (Akeneo) + Breadcrumb navegable (UX-06, UX-08) | 5 | P2 | S14 |
| US-ERP-01-06 | Inline edit mode — toggle View/Edit sin cambio de página (UX-09) | 8 | P2 | S14 |

**Total EP-ERP-01: 34 SP**

### Story US-ERP-01-01 — LifecycleStatusBadge + Quick Facts header

**Como** usuario comercial de MT,
**quiero** ver el estado del ciclo de vida del producto con color semántico y una fila de datos clave debajo del nombre,
**para** entender de un vistazo el estado operativo del producto sin navegar a otra pantalla.

**Criterios de aceptación:**
- `LifecycleStatusBadge`: `draft`=gris, `in_review`=amarillo, `active`=verde, `discontinued`=rojo (Tailwind semantic colors)
- Reemplaza el badge binario `active/inactive` actual en `ProductHeader`
- Quick Facts row: 4 KVPs — UoM Base · GTIN · Marca · Serie (debajo del nombre del producto)
- KVPs con valor `—` si el campo está vacío (no se ocultan)
- Responsive: 2 columnas en móvil, 4 columnas en desktop

**Referencia UX:** UX-01 (SAP Fiori Semantic Colors) + UX-02 (SAP Object Page KVP row)

**Archivos impactados:**
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`
- Nuevo: `mt-pricing-frontend/components/ui/lifecycle-status-badge.tsx`

---

### Story US-ERP-01-02 — Tab "Mercados" + "Activar mercado"

**Como** gerente comercial de MT,
**quiero** ver los mercados donde está activo un producto y poder activarlo en nuevos mercados,
**para** gestionar la disponibilidad por mercado al estilo D365 Released Products.

**Criterios de aceptación:**
- Nuevo tab "Mercados" en la página de detalle del producto
- Tabla de mercados con: país, moneda, precio local, tipo de impuesto, estado (activo/inactivo), fecha de activación
- Botón "Activar para este mercado" con dialog de confirmación (multi-step)
- Al activar: POST a nuevo endpoint `POST /api/v1/products/{sku}/releases`
- El endpoint crea un registro en tabla `product_releases` (a crear con migration Alembic)
- Backend: solo roles `comercial`, `gerente`, `ti` pueden crear releases

**Esquema `product_releases`:**
```sql
CREATE TABLE product_releases (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku          TEXT NOT NULL REFERENCES products(sku),
    market_code  TEXT NOT NULL,   -- 'UAE', 'KSA', 'MX'
    currency     CHAR(3),
    local_price  NUMERIC(18,4),
    tax_code     TEXT,
    status       TEXT DEFAULT 'active',
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    activated_by UUID REFERENCES auth.users(id),
    UNIQUE(sku, market_code)
);
```

**Referencia UX:** UX-03 (D365 Released Products) + UX-10 ("Release product" button)

**Archivos impactados:**
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`
- Nuevo: `mt-pricing-frontend/app/(app)/catalogo/[sku]/mercados/_client.tsx`
- `mt-pricing-backend/app/api/routes/products.py`
- Nueva migration Alembic: `20260513_105_product_releases.py`

---

### Story US-ERP-01-03 — Tab "Unidades" — UoM + conversiones

**Como** usuario del almacén de MT,
**quiero** ver la unidad de medida base y todas las conversiones del producto,
**para** operar correctamente las recepciones y despachos sin errores de unidad.

**Criterios de aceptación:**
- Nuevo tab "Unidades" en la página de detalle del producto
- Muestra `base_uom` del producto (campo ya existente)
- Tabla de conversiones: unidad alternativa, factor, dirección (de BOX a UNIT, ej: 1 BOX = 12 UNIT)
- Endpoint `GET /api/v1/products/{sku}/uom-conversions` (si no existe: retorna `[]`)
- Si no hay conversiones: mostrar mensaje "Solo unidad base configurada"
- Datos desde tabla `product_uom_conversions` (a crear con migration si no existe)

**Referencia UX:** UX-04 (SAP MM UoM alternativas)

---

### Story US-ERP-01-04 — GTIN en specs card + lifecycle chip en listado

**Como** usuario del catálogo de MT,
**quiero** ver el GTIN/EAN-13 en la ficha del producto y el estado de lifecycle en el listado,
**para** cumplir el estándar GS1 y tener visibilidad del ciclo de vida sin abrir cada producto.

**Criterios de aceptación:**
- GTIN mostrado en la card "Identidad / Global" dentro de la tab Specs, con validación visual EAN-13 (checkbox verde si 13 dígitos)
- Columna `lifecycle_status` en la tabla de productos del listado `/catalogo` con chip de color (mismo componente que US-ERP-01-01)
- Si `gtin` está vacío: mostrar `—` y chip "Sin GTIN" en amarillo

**Referencia UX:** UX-05 (GS1 GTIN) + UX-07 (SAP Fiori status column)

---

### Story US-ERP-01-05 — Completeness ring + Breadcrumb navegable

**Como** equipo de datos de MT,
**quiero** ver qué porcentaje del perfil del producto está completo y navegar con breadcrumb,
**para** priorizar el completado de datos y mejorar la navegación tipo Akeneo.

**Criterios de aceptación:**
- Ring de progreso circular (SVG) en el header del producto mostrando `completeness%`
- Tooltip del ring: lista de campos faltantes por grupo (datos básicos / traducciones / imagen / especificaciones)
- Lógica de completeness: definida por familia de producto (campo a cubrir más adelante con API)
- Breadcrumb: `Catálogo > [SKU] > [Tab activo]` navegable con links funcionales
- Breadcrumb visible en todas las sub-páginas del producto

**Referencia UX:** UX-06 (Akeneo completeness ring) + UX-08 (SAP/Akeneo breadcrumb)

---

### Story US-ERP-01-06 — Inline edit mode

**Como** editor de contenido de MT,
**quiero** editar los datos del producto sin navegar a una página separada,
**para** iterar rápido al estilo Akeneo sin perder el contexto de la vista.

**Criterios de aceptación:**
- Toggle "Editar / Ver" en el header del producto (solo para roles con permiso de edición)
- En modo edición: campos de texto se convierten en inputs editables in-place
- Botones "Guardar" y "Cancelar" aparecen en el header
- Al guardar: PATCH al endpoint existente, sin recarga de página completa
- Al cancelar: restaurar los valores originales sin llamada al servidor

**Referencia UX:** UX-09 (Akeneo inline edit mode)

---

## Epic EP-ERP-02 — Inventario v2: Movement Types, Trazabilidad y Almacenes

**Motivación:** EP-INV-01 implementó MAP/AVCO y posiciones de inventario básicas. EP-ERP-02
expande esto con los patrones SAP MM-IM: catálogo de tipos de movimiento, stock types diferenciados,
trazabilidad por lote, jerarquía de almacén y reposición automática. Encadena directamente con
la capa ERP adapter de EP-INV-01.

**Stack:** FastAPI + SQLAlchemy async + PostgreSQL + Celery

### Resumen de stories EP-ERP-02

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-02-01 | Movement Types catalog + stock_movements con accounting document | 8 | P0 | S13 |
| US-ERP-02-02 | Stock types diferenciados + inventory_positions 5D | 8 | P0 | S13 |
| US-ERP-02-03 | Lot tracking: inventory_lots + trazabilidad upstream/downstream | 8 | P1 | S14 |
| US-ERP-02-04 | Jerarquía almacén: Warehouse → Zone → Location (bin) | 5 | P1 | S14 |
| US-ERP-02-05 | FEFO automático en picking + alertas expiración (Celery) | 5 | P2 | S15 |
| US-ERP-02-06 | Replenishment params por producto-almacén + job ROP | 8 | P2 | S15 |
| US-ERP-02-07 | ABC classification automática (Celery mensual) + Cycle count | 8 | P2 | S15 |
| US-ERP-02-08 | Dashboard KPIs inventario: Turnover, DOH, Fill Rate, Stockout | 5 | P3 | S16 |

**Total EP-ERP-02: 55 SP**

### Story US-ERP-02-01 — Movement Types catalog + stock_movements

**Como** sistema de inventario de MT,
**quiero** registrar cada movimiento de stock con un tipo configurado y un documento contable vinculado,
**para** garantizar trazabilidad completa y cumplimiento con el principio "Movimiento = Documento".

**Criterios de aceptación:**
- Tabla `stock_movement_types` (code, name, direction: IN/OUT/TRANSFER, requires_reference, posts_accounting)
- Datos semilla: tipos inspirados en SAP (GR_PO=101, GI=261, TRANSFER=301, SCRAP=551, OPENING=561, REVERSAL=102)
- Cada movimiento crea un registro en `stock_movements` (movement_type_id, product_id, qty, lot_id, warehouse_id, reference_id, reference_type)
- Si `posts_accounting=true`: crear `journal_entries` vinculado con `source_movement_id`
- Reversión siempre por referencia: crea nuevo movimiento de signo contrario referenciando el original
- API: `GET /api/v1/inventory/movement-types`, `POST /api/v1/inventory/movements`

**Referencia investigación:** INV-01 + INV-02 + INV-03

---

### Story US-ERP-02-02 — Stock types diferenciados + inventory_positions 5D

**Como** planificador de MT,
**quiero** ver la posición de inventario desglosada por stock type y 5 dimensiones,
**para** separar el stock disponible del que está en cuarentena, bloqueado o en tránsito.

**Criterios de aceptación:**
- Campo `stock_type` en `inventory_positions`: `unrestricted` / `quality_inspection` / `restricted` / `in_transit`
- La posición de inventario es única por `(product_id, warehouse_id, location_id, lot_id, stock_type)` — índice UNIQUE compuesto
- Solo el stock `unrestricted` aparece en ATP check y queries de disponibilidad de ventas
- API: `GET /api/v1/inventory/positions?sku={sku}&warehouse_id={id}&stock_type=unrestricted`
- Migration Alembic: extender tabla `inventory_positions` existente con `stock_type` y `location_id`

**Referencia investigación:** INV-05 + INV-12

---

### Story US-ERP-02-03 — Lot tracking + trazabilidad upstream/downstream

**Como** responsable de calidad de MT,
**quiero** rastrear cada lote desde su PO de origen hasta los clientes que lo recibieron,
**para** poder ejecutar recalls de proveedor o notificar clientes en caso de defecto.

**Criterios de aceptación:**
- Tabla `inventory_lots` (lot_number, product_id, manufacture_date, expiry_date, country_of_origin, quality_status: released/hold/blocked, po_line_id)
- Al registrar GR de producto con tracking=LOT: crear/referenciar `lot_id`
- Query upstream: dado `lot_id` → PO line → vendor
- Query downstream: dado `lot_id` → sale_order_lines → customers
- API: `GET /api/v1/inventory/lots/{lot_id}/traceability`
- `quality_status` actualizable por roles `ti`, `gerente` (no `comercial`)

**Referencia investigación:** INV-06 + INV-07

---

### Story US-ERP-02-04 — Jerarquía almacén: Warehouse → Zone → Location

**Como** responsable de almacén de MT,
**quiero** una estructura jerárquica de almacenes con zonas y ubicaciones,
**para** saber exactamente dónde está cada producto dentro del almacén.

**Criterios de aceptación:**
- Tablas: `warehouses`, `warehouse_zones` (refrigerado, seco, peligroso, general), `warehouse_locations` (bin con código estructurado)
- Código de bin: `{warehouse_code}-{zone}-{fila}-{nivel}-{posición}` (ej: `WH1-A-03-02-B`)
- `inventory_positions.location_id` → FK a `warehouse_locations`
- CRUD admin: `GET/POST/PATCH /api/v1/warehouses` y sub-recursos
- Filtros en positions dashboard por warehouse y zone

**Referencia investigación:** INV-11 + INV-14

---

### Story US-ERP-02-05 — FEFO automático + alertas expiración

**Como** almacenero de MT,
**quiero** que el sistema proponga automáticamente el lote con fecha de expiración más próxima al generar un picking,
**para** cumplir el estándar FEFO y evitar merma por vencimiento.

**Criterios de aceptación:**
- Si `product.rotation_strategy = 'FEFO'` y `product.tracking = 'LOT'`: al generar pick, ordenar lotes por `expiry_date ASC`
- Job Celery diario: detectar lotes con `expiry_date < today + threshold_days`. Crear alerta `type='LOT_EXPIRY_WARNING'`
- `threshold_days` configurable por familia de producto (default: 30 días)
- API: `GET /api/v1/inventory/expiry-alerts` con lotes próximos a vencer agrupados por producto

**Referencia investigación:** INV-08 + INV-09

---

### Story US-ERP-02-06 — Replenishment params + job ROP automático

**Como** planificador de compras de MT,
**quiero** configurar parámetros de reposición (safety stock, ROP) por producto-almacén y que el sistema genere PRs automáticamente,
**para** evitar stockouts sin intervención manual diaria.

**Criterios de aceptación:**
- Tabla `replenishment_params` (product_id, warehouse_id, min_qty, max_qty, reorder_point, safety_stock, lead_time_days)
- Job Celery periódico (cada 4h): comparar stock `unrestricted` vs `reorder_point`. Si stock ≤ ROP: crear `purchase_requisition` automáticamente
- La PR creada referencia `replenishment_params` como origen y el proveedor preferido (Source List)
- Endpoint: `GET/PUT /api/v1/inventory/replenishment-params/{product_id}/{warehouse_id}`

**Referencia investigación:** INV-15 + INV-16

---

### Story US-ERP-02-07 — ABC classification + Cycle count schedule

**Como** jefe de almacén de MT,
**quiero** que el sistema clasifique automáticamente los SKUs por valor de consumo y genere programas de conteo cíclico,
**para** contar el 20% de SKUs críticos mensualmente en vez de hacer un inventario físico anual.

**Criterios de aceptación:**
- Job Celery mensual: calcular `annual_consumption_value = avg_price × qty_consumed_12m` por SKU
- Clasificar: A (top 80% valor acumulado), B (siguiente 15%), C (resto). Guardar en `products.abc_class`
- Generar `cycle_count_schedules`: A=mensual, B=trimestral, C=anual
- Tabla `cycle_counts` (location_id, product_id, scheduled_date, counted_qty, system_qty, variance, status)
- Si varianza > 2% o > $500: requerir aprobación de supervisor antes de ajustar

**Referencia investigación:** INV-17 + INV-18 + INV-19

---

### Story US-ERP-02-08 — Dashboard KPIs inventario

**Como** gerente de operaciones de MT,
**quiero** ver los KPIs de inventario en tiempo real,
**para** detectar problemas de fill rate, stockouts y rotación sin esperar reportes manuales.

**Criterios de aceptación:**
- Endpoint `/api/v1/inventory/kpis` con: Inventory Turnover, Days on Hand, Fill Rate, Stockout Rate%, Dead Stock%, Shrinkage Rate
- Filtrable por: warehouse_id, family, período (last_30d / last_90d / ytd)
- Cálculos basados en `stock_movements` y `inventory_positions`
- Frontend: página `/dashboard` → sección "Inventario" con 6 KPI cards y gráfico de tendencia

**Referencia investigación:** INV-23 + INV-24 + INV-25

---

## Epic EP-ERP-03 — Compras P2P: Purchase Requisitions, Approval Matrix, PIR

**Motivación:** El ciclo Procure-to-Pay comienza con la Purchase Requisition como primer punto de
control antes de comprometer gasto. Esta épica implementa: PR como entidad, matriz de aprobación
configurable, Purchasing Info Record (precio acordado con proveedor), y Three-Way Match automático
para verificación de facturas.

### Resumen de stories EP-ERP-03

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-03-01 | Purchase Requisition entity + status lifecycle + log inmutable | 8 | P0 | S13 |
| US-ERP-03-02 | Approval matrix configurable + escalación automática (Celery) | 8 | P0 | S14 |
| US-ERP-03-03 | PO types + Purchasing Info Record (precio proveedor-producto) | 5 | P1 | S14 |
| US-ERP-03-04 | Three-way match PO↔GR↔Invoice + tolerance keys + payment block | 8 | P1 | S15 |
| US-ERP-03-05 | Source List (proveedores aprobados) + RFQ básico con comparativa | 8 | P2 | S15 |
| US-ERP-03-06 | Dashboard KPIs procurement + spend analysis + vendor scorecard | 5 | P2 | S16 |

**Total EP-ERP-03: 42 SP**

### Story US-ERP-03-01 — Purchase Requisition entity + lifecycle

**Como** cualquier empleado de MT con acceso al sistema,
**quiero** crear una solicitud de compra formal antes de comprometer gasto,
**para** que el sistema controle el gasto desde el origen con un flujo de aprobación.

**Criterios de aceptación:**
- Tabla `purchase_requisitions` (requester_id, product_id, qty, uom, required_date, cost_center_id, suggested_vendor_id, status, estimated_amount)
- Status lifecycle: `draft` → `pending_approval` → `approved` → `converted_to_po` / `rejected` / `cancelled`
- Solo PRs en estado `approved` pueden convertirse en PO
- Tabla `approval_decisions` (document_id, approver_id, action: APPROVE/REJECT, reason, timestamp) — inmutable (INSERT only, no UPDATE/DELETE)
- API: `POST /api/v1/procurement/requisitions`, `PATCH /api/v1/procurement/requisitions/{id}/submit`
- RLS: el usuario solo ve sus propias PRs; aprobadores ven las que les corresponden

**Referencia investigación:** PRC-01 + PRC-02 + PRC-07

---

### Story US-ERP-03-02 — Approval matrix configurable + escalación

**Como** CFO de MT,
**quiero** configurar una matriz de aprobación por monto y categoría sin cambiar código,
**para** que las PRs se enruten automáticamente al aprobador correcto y se escalen si no responden.

**Criterios de aceptación:**
- Tabla `approval_rules` (document_type, min_amount, max_amount, category_id, approver_role, approver_user_id, timeout_hours)
- Al someter PR: evaluar reglas en orden de `min_amount ASC`. Asignar aprobador.
- Job Celery Beat (cada hora): detectar aprobaciones con `created_at + timeout_hours < now`. Escalar al siguiente nivel.
- Al aprobar/rechazar: notificación in-app al solicitante con razón
- Configuración mínima: < $1,000 → auto-aprobado; $1k–$10k → manager; > $10k → CFO

**Referencia investigación:** PRC-04 + PRC-05 + PRC-06

---

### Story US-ERP-03-03 — PO types + Purchasing Info Record

**Como** comprador de MT,
**quiero** clasificar mis POs por tipo y que el sistema proponga el precio del proveedor automáticamente,
**para** evitar introducir precios manualmente y mantener consistencia con las condiciones negociadas.

**Criterios de aceptación:**
- Campo `po_type` en `purchase_orders`: `STANDARD` / `BLANKET` / `CONTRACT` / `SCHEDULING`
- Tabla `vendor_product_conditions` (Purchasing Info Record): vendor_id, product_id, price, uom, moq, lead_time_days, valid_from, valid_to
- Al crear línea de PO: si existe PIR vigente → pre-llenar precio automáticamente
- UI: indicador visual "Precio desde PIR" vs "Precio manual"
- CRUD: `GET/POST/PUT /api/v1/procurement/vendor-conditions`

**Referencia investigación:** PRC-08 + PRC-11

---

### Story US-ERP-03-04 — Three-way match + tolerance keys + payment block

**Como** equipo de cuentas por pagar de MT,
**quiero** que el sistema verifique automáticamente la factura contra la PO y GR con tolerancias configurables,
**para** bloquear pagos solo cuando hay diferencias reales y no desperdiciar tiempo en revisiones manuales.

**Criterios de aceptación:**
- Al registrar `vendor_invoice`: comparar qty/precio con PO y GR correspondientes
- Tabla `invoice_tolerances` (document_type, vendor_category, tolerance_key, absolute_limit, pct_limit)
- Status match: `matched` / `tolerance_ok` / `blocked`
- Si `status = blocked`: `payment_block = true`. Para liberar: seleccionar razón obligatoria + comentario (auditado)
- API: `POST /api/v1/procurement/invoices/{id}/match`

**Referencia investigación:** PRC-17 + PRC-18 + PRC-20

---

### Story US-ERP-03-05 — Source List + RFQ básico

**Como** comprador de MT,
**quiero** mantener una lista de proveedores aprobados por producto y solicitar cotizaciones comparativas,
**para** controlar el gasto maverick y elegir el mejor proveedor para cada compra.

**Criterios de aceptación:**
- Tabla `product_approved_vendors` (Source List): product_id, warehouse_id, vendor_id, is_preferred, is_blocked, valid_from, valid_to
- Si `mandatory=true` en la config: bloquear POs a vendedores fuera de la lista
- Tablas `rfqs` + `rfq_lines` + `vendor_quotations`
- Endpoint de comparación: `GET /api/v1/procurement/rfqs/{id}/comparison` → tabla por proveedor ordenada por precio
- Conversión ganadora → PO con trazabilidad RFQ → PO en `purchase_orders.rfq_id`

**Referencia investigación:** PRC-12 + PRC-14 + PRC-16

---

### Story US-ERP-03-06 — Dashboard KPIs procurement + spend analysis

**Como** director de compras de MT,
**quiero** ver los KPIs de compras y el análisis de gasto en tiempo real,
**para** identificar proveedores de bajo desempeño y gasto maverick sin esperar reportes manuales.

**Criterios de aceptación:**
- Endpoints: PO Cycle Time, Vendor OTD%, Invoice Processing Time, Spend Under Management%, Maverick Spend%
- `/api/v1/procurement/spend-analysis` con groupBy: vendor / category / month / cost_center
- Vendor scorecard: OTD% + % GRs sin devolución + cumplimiento de precio vs PIR. Actualizado mensualmente (Celery)
- Frontend: dashboard `/compras` con 5 KPI cards + tabla de spend analysis filtrable

**Referencia investigación:** PRC-21 + PRC-22 + PRC-23

---

## Epic EP-ERP-04 — Ventas O2C: ATP, Credit Management, RMA

**Motivación:** El ciclo Order-to-Cash de MT necesita tipos de documento de venta, verificación
de disponibilidad en tiempo real (ATP), gestión de crédito de clientes, outbound delivery y
gestión de devoluciones (RMA) para operar como un ERP de distribución maduro.

### Resumen de stories EP-ERP-04

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-04-01 | SO types + document chain reference completa (VEN-01, VEN-03) | 5 | P1 | S14 |
| US-ERP-04-02 | ATP check en SO + soft reservation de stock (VEN-05, VEN-06, VEN-08) | 13 | P1 | S14 |
| US-ERP-04-03 | Credit management: check automático + auto-release (VEN-09, VEN-10, VEN-11) | 8 | P1 | S15 |
| US-ERP-04-04 | Outbound Delivery entity + Goods Issue → inventario + AR (VEN-12, VEN-16) | 8 | P0 | S15 |
| US-ERP-04-05 | Returns RMA + Return Delivery + Credit Memo automático (VEN-17, VEN-18, VEN-19) | 8 | P1 | S15 |
| US-ERP-04-06 | Dashboard O2C KPIs + Backorder report (VEN-20, VEN-21) | 5 | P2 | S16 |

**Total EP-ERP-04: 47 SP**

### Story US-ERP-04-01 — SO types + document chain

**Como** sistema de ventas de MT,
**quiero** clasificar las órdenes de venta por tipo y mantener encadenados todos los documentos del ciclo,
**para** navegar de cualquier documento (factura, delivery) al pedido original con un query.

**Criterios de aceptación:**
- Campo `order_type` en `sales_orders`: `STANDARD` / `RUSH` / `CASH` / `CONTRACT_RELEASE` / `RETURN`
- FK `quotation_id` en SO (opcional — si viene de una cotización)
- FK `so_id` en `outbound_deliveries`, FK `delivery_id` en `invoices`
- Endpoint de cadena: `GET /api/v1/sales/orders/{id}/chain` retorna Quotation→SO→Delivery→Invoice en un objeto

**Referencia investigación:** VEN-01 + VEN-03

---

### Story US-ERP-04-02 — ATP check + soft reservation

**Como** vendedor de MT al crear un pedido,
**quiero** saber si el producto estará disponible en la fecha solicitada y reservar el stock comprometido,
**para** dar una fecha de entrega fiable al cliente y evitar vender más stock del que existe.

**Criterios de aceptación:**
- `POST /api/v1/sales/orders/{id}/atp-check`: calcula `ATP Qty = stock_unrestricted + GRs_planeados − reservas_activas`
- Si `ATP Qty ≥ qty_requested`: confirmar fecha; si no: proponer `first_available_date`
- `checking_rules` configurable por producto: incluir/excluir safety stock, GRs planeados, stock en QA
- Al confirmar línea de SO: crear `stock_reservations` (so_line_id, product_id, warehouse_id, qty, expiry)
- Las reservas reducen el ATP disponible para nuevos pedidos
- Job Celery al procesar GR: re-evaluar backorders y actualizar fechas

**Referencia investigación:** VEN-05 + VEN-06 + VEN-07 + VEN-08

---

### Story US-ERP-04-03 — Credit management

**Como** gerente de crédito de MT,
**quiero** que el sistema bloquee automáticamente pedidos que excedan el límite de crédito del cliente,
**para** controlar la exposición crediticia antes de despachar, no después.

**Criterios de aceptación:**
- Campo `credit_limit` en `customers` + reglas configurables (límite excedido, deuda vencida, días máx vencido)
- Al crear/modificar SO: evaluar crédito. Si falla: `status = 'credit_hold'`, notificación al credit manager
- Endpoint: `POST /api/v1/sales/orders/{id}/release-credit-hold` (solo gerente/ti) con razón obligatoria
- Job Celery al registrar pago: re-evaluar crédito. Si deuda < límite: auto-liberar SOs en `credit_hold`
- Exclusion rule: órdenes < $500 no pasan credit check (configurable)

**Referencia investigación:** VEN-09 + VEN-10 + VEN-11

---

### Story US-ERP-04-04 — Outbound Delivery + Goods Issue

**Como** almacenero de MT,
**quiero** gestionar el proceso de picking, packing y despacho como una entidad separada del pedido,
**para** tener visibilidad completa del estado de fulfillment y disparar la reducción de inventario solo al confirmar el envío.

**Criterios de aceptación:**
- Tabla `outbound_deliveries` (so_id, warehouse_id, status: pending_pick/picking/packed/goods_issued)
- Al confirmar `goods_issued`: crear `stock_movement` tipo GI (reduce stock `unrestricted`)
- El GI también abre el AR del cliente en `customer_open_items` y habilita la creación de billing
- Partial delivery: configurable por SO (`partial_delivery_allowed = true/false`)
- API: `POST /api/v1/sales/deliveries`, `PATCH /api/v1/sales/deliveries/{id}/goods-issue`

**Referencia investigación:** VEN-12 + VEN-15 + VEN-16

---

### Story US-ERP-04-05 — Returns RMA + Credit Memo

**Como** equipo de atención al cliente de MT,
**quiero** gestionar devoluciones de clientes con un número RMA y emitir créditos automáticamente,
**para** resolver devoluciones rápido sin coordinación manual entre ventas, almacén y finanzas.

**Criterios de aceptación:**
- Tabla `return_orders` (rma_number auto-generado, original_so_id, reason_code: damaged/wrong_item/quality/other, status)
- Al recibir mercadería devuelta: registrar `return_delivery` con decisión: `restock` / `scrap` / `repair`
- `restock` → crea stock_movement de entrada al almacén (tipo GR-RETURN)
- `scrap` → crea stock_movement de baja (tipo SCRAP)
- Al aprobar devolución: crear automáticamente `credit_memo` referenciando la factura original

**Referencia investigación:** VEN-17 + VEN-18 + VEN-19

---

### Story US-ERP-04-06 — Dashboard O2C KPIs + Backorder report

**Como** director comercial de MT,
**quiero** ver los KPIs del ciclo de ventas y backorders en tiempo real,
**para** gestionar proactivamente el fill rate y las fechas de entrega sin esperar reportes.

**Criterios de aceptación:**
- Endpoint `/api/v1/sales/kpis`: Perfect Order Rate, Order Fulfillment Cycle Time, Fill Rate%, Backorder Rate%, Return Rate%, Quote-to-Order Rate%
- `/api/v1/sales/backorders`: SOs con líneas en ATP_FAIL o partial, con fecha prometida vs nueva fecha estimada
- Frontend: dashboard `/ventas` con KPI cards + tabla de backorders filtrable por cliente/producto

**Referencia investigación:** VEN-20 + VEN-21

---

## Epic EP-ERP-05 — Billing & Facturación: Invoice Types, Dunning, e-Invoicing

**Motivación:** El módulo de billing debe emitir facturas dentro de 24h del GI, con tipos correctos
(F2, G2, Cancellation), asientos automáticos, dunning por aging buckets y cumplimiento con CFDI 4.0
(México) y ZATCA Fatoora (Arabia Saudita). El DSO se reduce directamente con estos cambios.

### Resumen de stories EP-ERP-05

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-05-01 | Billing types + document chain + precio copiado del SO (BIL-01,02,03) | 5 | P0 | S14 |
| US-ERP-05-02 | Asientos FI automáticos + desglose revenue + link accounting doc (BIL-05,06,07) | 8 | P0 | S14 |
| US-ERP-05-03 | Dunning automático por aging buckets + payment terms (BIL-12, BIL-13) | 8 | P1 | S15 |
| US-ERP-05-04 | CFDI 4.0 + ZATCA Fatoora + tabla e_invoice_submissions (BIL-08,09,10,11) | 13 | P0 | S15 |
| US-ERP-05-05 | AR Aging Report tiempo real + promesas de pago (BIL-14, BIL-15) | 5 | P2 | S16 |
| US-ERP-05-06 | Dashboard KPIs billing: DSO, CEI, Time to Invoice + alerta 24h (BIL-19, BIL-20) | 3 | P2 | S16 |

**Total EP-ERP-05: 42 SP**

### Story US-ERP-05-01 — Billing types + document chain + precio copiado

**Como** sistema de facturación de MT,
**quiero** clasificar las facturas por tipo y garantizar que el precio de la factura coincide exactamente con el del pedido,
**para** evitar discrepancias de precio post-factura y mantener la cadena de documentos rastreable.

**Criterios de aceptación:**
- Campo `billing_type` en `invoices`: `STANDARD` / `PROFORMA` / `CREDIT_MEMO` / `DEBIT_MEMO` / `CANCELLATION`
- `PROFORMA`: no genera asiento contable (informativo para aduanas)
- `CANCELLATION`: revierte exactamente el asiento del documento original
- `invoices.delivery_id` + `invoices.so_id` obligatorios (NOT NULL)
- Al crear invoice: copiar `unit_price`, `discount`, `tax_amount` desde SO lines. El pricing engine NO se re-ejecuta.
- `credit_memos.original_invoice_id` NOT NULL

**Referencia investigación:** BIL-01 + BIL-02 + BIL-03 + BIL-04

---

### Story US-ERP-05-02 — Asientos FI automáticos + desglose revenue

**Como** equipo de contabilidad de MT,
**quiero** que confirmar una factura genere automáticamente el asiento contable sin intervención manual,
**para** eliminar el paso manual de registro y garantizar consistencia entre billing y contabilidad.

**Criterios de aceptación:**
- Al cambiar `invoice.status` a `posted`: crear automáticamente en `financial_entries`:
  - DR: Accounts Receivable (cliente) — importe total
  - CR: Revenue Account (por línea de producto) — importe neto
  - CR: Tax Payable — importe de impuesto
- `invoices.accounting_document_id` → FK a `financial_entries`. Inmutable una vez contabilizado.
- Credit Memo: asiento inverso automático
- Cancellation: reversión exacta del asiento original

**Referencia investigación:** BIL-05 + BIL-06 + BIL-07

---

### Story US-ERP-05-03 — Dunning automático + payment terms

**Como** equipo de cobranza de MT,
**quiero** que el sistema envíe recordatorios de pago automáticamente según el tiempo de vencimiento,
**para** reducir el DSO sin depender de que alguien recuerde enviar emails manualmente.

**Criterios de aceptación:**
- Tabla `payment_terms` (code, net_days, discount_pct, discount_days) — configurable por cliente
- Job Celery diario: clasificar facturas vencidas en 4 buckets (1-30 / 31-60 / 61-90 / +90 días)
- Enviar email automático por nivel: Nivel 1 (cortés), 2 (firme), 3 (formal con intereses), 4 (legal)
- Nivel 4: alerta adicional a equipo legal/dirección
- Segmentación: clientes VIP reciben cadencia más lenta y personalizada (campo `customer.dunning_tier`)

**Referencia investigación:** BIL-12 + BIL-13

---

### Story US-ERP-05-04 — CFDI 4.0 + ZATCA Fatoora + e_invoice_submissions

**Como** sistema de facturación de MT,
**quiero** generar facturas electrónicas válidas para México (CFDI 4.0) y Arabia Saudita (ZATCA Fatoora),
**para** cumplir con las obligaciones legales de e-invoicing con sanciones si no se cumple.

**Criterios de aceptación:**
- Tabla `e_invoice_submissions` (invoice_id, authority: SAT/ZATCA, submission_timestamp, response_code, uuid_fiscal, status). INSERT-only, sin UPDATE/DELETE. Retención mínima 5 años.
- **CFDI 4.0**: generar XML → enviar a PAC configurado → recibir Timbre Fiscal Digital → guardar UUID + XML sellado. El PAC es configurable vía env var.
- **ZATCA Fatoora**: clearance en tiempo real para B2B. La invoice NO se envía al cliente hasta recibir aprobación ZATCA. UUID + QR code + crypto stamp obligatorios.
- PDF fiscal con: RFC/TRN emisor y receptor, UUID fiscal, desglose de impuestos, condiciones de pago, datos bancarios.
- Job de reintento: si falla el envío al PAC/ZATCA → reintentar máx 3 veces con backoff exponencial.

**Referencia investigación:** BIL-08 + BIL-09 + BIL-10 + BIL-11

---

### Story US-ERP-05-05 — AR Aging Report + promesas de pago

**Como** gerente de cobranza de MT,
**quiero** ver el aging de cuentas por cobrar en tiempo real y registrar promesas de pago de clientes morosos,
**para** tener visibilidad completa de la exposición crediticia y hacer seguimiento de compromisos.

**Criterios de aceptación:**
- Endpoint `/api/v1/finance/ar-aging` con 6 buckets (Current/1-30/31-60/61-90/91-120/+120). Filtrable por cliente, vendedor, período.
- Tabla `payment_promises` (customer_id, invoice_id, promised_date, promised_amount, agent_id)
- Job Celery: si `promised_date` pasó y factura sigue abierta → alerta al agente
- Frontend: página `/cobranza` con aging buckets + tabla de promesas pendientes

**Referencia investigación:** BIL-14 + BIL-15

---

### Story US-ERP-05-06 — Dashboard KPIs billing + alerta 24h

**Como** director financiero de MT,
**quiero** ver los KPIs de facturación y ser alertado cuando una entrega no genera factura en 24h,
**para** reducir el DSO y garantizar que toda entrega se factura al día.

**Criterios de aceptación:**
- Endpoint `/api/v1/finance/billing-kpis`: DSO, CEI, AR Turnover, Bad Debt Ratio, Invoice Accuracy Rate, Time to Invoice, E-Invoice Compliance Rate%
- Job Celery: detectar deliveries con `goods_issued > 24h` sin invoice generada → notificar al billing team
- Frontend: sección "Billing" en dashboard con KPI cards y gráfico de tendencia mensual

**Referencia investigación:** BIL-19 + BIL-20

---

## Epic EP-ERP-06 — Finanzas: Universal Journal, CoA, Profit Centers, Period Close

**Motivación:** El sistema actual carece de un General Ledger formal. Para operar como ERP de
distribución bajo IFRS y cumplir con UAE CIT (9%), se necesita: plan de cuentas standardizado,
control de períodos, Universal Journal (single source of truth), centros de costo y ganancia,
cierre de período automatizable, y estados financieros en tiempo real.

### Resumen de stories EP-ERP-06

| Story | Título | SP | Prioridad | Sprint |
|-------|--------|----|-----------|--------|
| US-ERP-06-01 | Chart of Accounts (200 cuentas) + Posting Periods control (FIN-02,03) | 5 | P0 | S13 |
| US-ERP-06-02 | Cost Centers hierarchy + Profit Centers básicos (FIN-09,10) | 5 | P0 | S13 |
| US-ERP-06-03 | Universal Journal — financial_entries table + balancing constraint (FIN-01) | 8 | P0 | S14 |
| US-ERP-06-04 | AP Aging automático + Payment Run configurable (FIN-04,05) | 8 | P1 | S14 |
| US-ERP-06-05 | Standard Cost por SKU + varianza de precio de compra (FIN-11,12) | 8 | P1 | S15 |
| US-ERP-06-06 | P&L real-time (vista materializada) + Balance Sheet reconciliación (FIN-15,16) | 8 | P1 | S15 |
| US-ERP-06-07 | Period Close Checklist automatizado + UAE CIT provisioning (FIN-14,19) | 5 | P0 | S15 |
| US-ERP-06-08 | FX Revaluation al cierre + Journal Entry SoD controls (FIN-20,21) | 5 | P1 | S16 |
| US-ERP-06-09 | CO-PA contribution margin + Cash Flow + Budget vs Actual (FIN-13,17,22) | 8 | P2 | S16 |

**Total EP-ERP-06: 60 SP**

### Story US-ERP-06-01 — Chart of Accounts + Posting Periods

**Como** controller de MT,
**quiero** un plan de cuentas standardizado (máx 200 cuentas) y control de períodos contables,
**para** que ningún asiento se pueda postear a un período ya cerrado y el cierre mensual sea reproducible.

**Criterios de aceptación:**
- Tabla `gl_accounts` (account_code VARCHAR(10) UNIQUE, account_name, account_type: ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE, normal_balance: DEBIT/CREDIT, is_reconciling, is_active)
- Rango estándar: 1000-1999 Activos, 3000-3999 Pasivos, 5000-5999 Revenue, 6000-6999 COGS, 7000-7999 OpEx, 9000-9999 Clearing
- Tabla `posting_periods` (fiscal_period VARCHAR(7) '2026-05', account_type CHAR(1), status: OPEN/SOFT_CLOSED/CLOSED)
- Validación en cada `INSERT` a `financial_entries`: si período está CLOSED → error 422
- Migration Alembic: crear tablas + seed de 200 cuentas base
- API: `GET /api/v1/finance/accounts`, `GET/PATCH /api/v1/finance/posting-periods`

**Referencia investigación:** FIN-02 + FIN-03

---

### Story US-ERP-06-02 — Cost Centers + Profit Centers

**Como** controller de MT,
**quiero** una jerarquía de centros de costo por función y profit centers por segmento de negocio,
**para** ver el P&L por canal (B2C UAE, B2C KSA) y controlar gastos por departamento.

**Criterios de aceptación:**
- Tabla `cost_centers` (cc_code, cc_name, parent_id → self-ref, cc_type: PRODUCTION/SERVICE/ADMIN, responsible_id, valid_from, valid_to)
- Jerarquía mínima: Ventas (1010), Marketing (1020), Almacén (2010), Logística (2020), IT (3010), G&A (4010)
- Tabla `profit_centers` (pc_code, pc_name, business_area: B2C/B2B/INTERNAL, responsible_id)
- Profit centers mínimos: `PC_B2C_AE` (UAE), `PC_B2C_SA` (KSA), `PC_INTERN`
- `financial_entries.cost_center_id` + `financial_entries.profit_center_id` — FK opcionales pero validadas
- API: `GET/POST /api/v1/finance/cost-centers`, `GET/POST /api/v1/finance/profit-centers`

**Referencia investigación:** FIN-09 + FIN-10

---

### Story US-ERP-06-03 — Universal Journal (financial_entries)

**Como** sistema contable de MT,
**quiero** una única tabla de asientos que contenga todas las dimensiones (GL + CC + PC + proyecto) en una sola fila,
**para** eliminar la reconciliación entre módulos y tener una sola fuente de verdad para todos los reportes financieros.

**Criterios de aceptación:**
- Tabla `financial_entries` según diseño completo del archivo de investigación FIN (con índices)
- Campos clave: `entry_number`, `journal_date`, `posting_period`, `entry_type`, `source_module`, `source_document`, `gl_account_id`, `cost_center_id`, `profit_center_id`, `debit_amount`, `credit_amount`, `currency_code`, `amount_local`, `fx_rate`, `preparer_id`, `reviewer_id`, `approver_id`
- Trigger de balance: validar que la suma de `debit_amount = credit_amount` por `source_document`
- Índices: `posting_period`, `gl_account_id`, `journal_date`
- Los módulos billing, compras e inventario inscriben sus asientos aquí vía `source_module`

**Referencia investigación:** FIN-01 + arquitectura SQL del archivo

---

### Story US-ERP-06-04 — AP Aging + Payment Run

**Como** equipo de cuentas por pagar de MT,
**quiero** ver el aging de proveedores y programar un payment run automático,
**para** pagar a tiempo y capturar descuentos por pronto pago sin coordinación manual.

**Criterios de aceptación:**
- Tabla `vendor_open_items` según diseño del archivo de investigación FIN
- Endpoint `/api/v1/finance/ap-aging` con 5 buckets (current/1-30/31-60/61-90/90+). DPO calculado.
- Tabla `payment_runs` (status: draft→proposed→approved→executed). Generar archivo bancario CSV/MT940 al ejecutar.
- Pre-step Proposal obligatorio: mostrar qué se va a pagar antes de ejecutar (revisable y editable)
- Descuento por pronto pago: si `payment_date <= discount_days_deadline` → aplicar `discount_pct` automáticamente

**Referencia investigación:** FIN-04 + FIN-05 + FIN-06

---

### Story US-ERP-06-05 — Standard Cost + varianza de precio

**Como** controller de costos de MT,
**quiero** definir un costo estándar por SKU y que las discrepancias de precio en las recepciones se registren automáticamente,
**para** tener visibilidad de la varianza entre precio negociado y precio real de compra.

**Criterios de aceptación:**
- Tabla `product_standard_costs` (product_id, valid_from, valid_to, material_cost, freight_cost, duty_cost, handling_cost, total_standard GENERATED, currency_code, status)
- Al procesar GR: si `po_price ≠ standard_cost` → postear automáticamente varianza a cuenta `8000 Price Difference`
- Alerta si varianza > 5% del standard → notificar al controller
- API: `GET/POST /api/v1/finance/standard-costs/{product_id}`

**Referencia investigación:** FIN-11 + FIN-12

---

### Story US-ERP-06-06 — P&L real-time + Balance Sheet reconciliation

**Como** CFO de MT,
**quiero** ver el P&L en tiempo real sin esperar al cierre mensual y recibir alertas si los sub-ledgers no cuadran con el GL,
**para** tomar decisiones comerciales con datos actualizados y detectar errores contables inmediatamente.

**Criterios de aceptación:**
- Vista materializada `income_statement_view` con P&L completo: Revenue → Gross Profit → EBITDA → Net Income. Refrescada on-demand.
- Drill-down desde cualquier línea P&L al `financial_entries` de origen
- Job Celery diario: para cuentas reconciliables (`is_reconciling=true`): verificar `SUM(open_items) = gl_balance`. Alerta si diferencia > 0.
- API: `GET /api/v1/finance/income-statement?period=2026-05&profit_center=PC_B2C_AE`

**Referencia investigación:** FIN-15 + FIN-16

---

### Story US-ERP-06-07 — Period Close Checklist + UAE CIT provisioning

**Como** controller de MT,
**quiero** un checklist automatizado del cierre mensual y la provisión de impuesto corporativo UAE calculada automáticamente,
**para** cerrar el mes en 3 días hábiles y cumplir con el UAE CIT del 9%.

**Criterios de aceptación:**
- Tabla `period_close_tasks` (order, module, task_name, auto, deadline_offset, status, executed_at, result)
- Celery Beat dispara tareas automáticas en orden: inventory cutoff → depreciation → FX revaluation → accruals → close MM → close FI → CO allocations → generate financials
- UAE CIT provisioning: al cierre mensual, si `EBT > 0`: calcular `provision = max(0, (EBT - 375000 AED threshold) * 0.09)` y postear asiento automático
- Dashboard `/cierre-mensual` con checklist en tiempo real: semáforo verde/rojo por tarea

**Referencia investigación:** FIN-14 + FIN-19

---

### Story US-ERP-06-08 — FX Revaluation + Journal SoD controls

**Como** controller de MT,
**quiero** revaluar los saldos en moneda extranjera al cierre y controlar que los asientos manuales tengan aprobación,
**para** cumplir con IAS 21 (FX) y segregación de funciones contables (SoD).

**Criterios de aceptación:**
- FX Revaluation: al cierre de mes, revaluar saldos AR/AP/Bank en moneda extranjera al tipo de cambio del día. Postear DR/CR a cuenta `8000 FX Gain-Loss`.
- Solo para cierre contable (no afecta operaciones diarias)
- Journal Entry SoD: 3 roles separados en `journal_approvals`: Preparer → Reviewer → Approver. Un usuario no puede ser Preparer y Approver del mismo asiento.
- Sin auto-aprobación posible. Los asientos manuales sin aprobación quedan en `DRAFT` y no impactan reportes.

**Referencia investigación:** FIN-20 + FIN-21

---

### Story US-ERP-06-09 — CO-PA + Cash Flow + Budget vs Actual

**Como** equipo directivo de MT,
**quiero** ver la contribución marginal por canal, el estado de flujo de caja de 13 semanas y la varianza presupuestaria,
**para** tomar decisiones estratégicas de pricing y canal con datos financieros completos.

**Criterios de aceptación:**
- Vista `copa_summary` (materializada): Revenue − COGS − Freight = Contribution Margin, agrupado por (customer_id, product_id, sales_channel, country, profit_center, period)
- Cash Flow Statement (método indirecto): Net Income + Depreciation + ΔAR + ΔAP + ΔInventory = OCF. Calculado desde `financial_entries`.
- Forecast 13 semanas: AR aging × probabilidad de cobro + AP aging × payment runs programados = posición neta semanal. Alerta si < 3 meses de OpEx.
- Tablas `budget_versions` + `budget_lines` según diseño del archivo de investigación FIN.
- Dashboard Budget vs Actual: alerta si varianza adversa > 10% en gastos.

**Referencia investigación:** FIN-13 + FIN-17 + FIN-18 + FIN-22

---

## Selección Sprint S13 — Quick Wins + Foundation

**Objetivo Sprint 13:** Establecer la base financiera, UX inmediata y fundamentos de inventario v2.

| Story | Epic | SP | Módulo |
|-------|------|----|--------|
| US-ERP-01-01 | EP-ERP-01 | 5 | UX — LifecycleStatusBadge + Quick Facts |
| US-ERP-01-02 | EP-ERP-01 | 8 | UX — Tab Mercados + Activar mercado |
| US-ERP-01-03 | EP-ERP-01 | 5 | UX — Tab Unidades UoM |
| US-ERP-01-04 | EP-ERP-01 | 3 | UX — GTIN + lifecycle chip listado |
| US-ERP-02-01 | EP-ERP-02 | 8 | INV — Movement Types + stock_movements |
| US-ERP-02-02 | EP-ERP-02 | 8 | INV — Stock types + positions 5D |
| US-ERP-03-01 | EP-ERP-03 | 8 | PRC — Purchase Requisition entity |
| US-ERP-06-01 | EP-ERP-06 | 5 | FIN — Chart of Accounts + Posting Periods |
| US-ERP-06-02 | EP-ERP-06 | 5 | FIN — Cost Centers + Profit Centers |

**Total S13: 55 SP** (dentro del target de 50-60 SP para un sprint de 2 semanas)

---

## Retrospectiva por épica (placeholder)

- epic-EP-ERP-01-retrospective: optional
- epic-EP-ERP-02-retrospective: optional
- epic-EP-ERP-03-retrospective: optional
- epic-EP-ERP-04-retrospective: optional
- epic-EP-ERP-05-retrospective: optional
- epic-EP-ERP-06-retrospective: optional
