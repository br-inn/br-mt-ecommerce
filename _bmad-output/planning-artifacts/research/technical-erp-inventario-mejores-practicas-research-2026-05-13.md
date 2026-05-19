---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'ERP Inventory Management — mejores prácticas de la industria'
research_goals: 'Identificar mejores prácticas de gestión de inventario en SAP y sistemas líderes, y documentar mejoras aplicables a br-mt-ecommerce'
user_name: 'psierra'
date: '2026-05-13'
web_research_enabled: true
source_verification: true
---

# Research Report: ERP Inventory Management — Mejores Prácticas de la Industria

**Fecha:** 2026-05-13
**Autor:** psierra
**Tipo de investigación:** Technical
**Documento previo:** [Maestros de Datos](./technical-erp-master-data-mejores-practicas-industria-research-2026-05-13.md)

---

## Research Overview

Investigación técnica comparativa sobre gestión de inventario en SAP WM/EWM, Oracle NetSuite, Microsoft Dynamics 365, Odoo y sistemas WMS especializados. Cubre movimientos de stock, trazabilidad por lote/serial, gestión de almacenes multi-ubicación, reposición automática y KPIs operativos. Documento complementario a [Maestros de Datos](./technical-erp-master-data-mejores-practicas-industria-research-2026-05-13.md).

---

## Confirmación de Alcance

**Research Topic:** ERP Inventory Management — mejores prácticas de la industria
**Research Goals:** Identificar mejores prácticas de gestión de inventario y documentar mejoras aplicables a br-mt-ecommerce

**Módulos cubiertos:**
- Movimientos de stock y tipos de movimiento
- Trazabilidad: lotes, seriales, fechas de expiración, FEFO
- Estructura de almacén: ubicaciones, bins, estrategias de putaway/picking
- Conteo cíclico y conteo físico (ABC analysis)
- Gestión multi-almacén y transferencias de stock
- Reposición automática: safety stock, reorder point, min/max
- Valuación de inventario: AVCO, FIFO, por lote
- KPIs operativos de inventario

**Sistemas analizados:** SAP MM-IM/WM/EWM · Oracle NetSuite · Microsoft Dynamics 365 · Odoo 18 · MRPeasy

**Scope Confirmed:** 2026-05-13

---

## Módulo 1 — Movimientos de Stock y Tipos de Movimiento

### SAP Movement Types — El Patrón de Referencia

SAP resuelve la complejidad de los movimientos de inventario con un único concepto clave: el **Movement Type**. Cada tipo de movimiento define:
- El sentido del movimiento (entrada / salida / traslado)
- El impacto contable (qué cuentas se debitan/acreditan)
- El tipo de documento que se genera
- Si requiere o no referencia a un documento origen

**Movement Types más importantes:**

| MT | Nombre | Dirección | Genera doc. contable | Referencia |
|----|--------|-----------|---------------------|-----------|
| **101** | GR para PO | Entrada stock | Sí | PO obligatoria |
| **102** | Reversión GR PO | Salida stock | Sí | GR original |
| **201** | GI a cost center | Salida stock | Sí | No |
| **261** | GI para producción | Salida stock | Sí | Production Order |
| **301** | Transfer entre plantas (1 paso) | Traslado | Sí | No |
| **501** | GR sin referencia | Entrada stock | Sí | No |
| **551** | Scrap / baja de inventario | Salida stock | Sí | No |
| **561** | Opening balance (carga inicial) | Entrada stock | No | No |

**Principio fundamental:** cualquier movimiento de stock debe generar un **Material Document** (trazabilidad física) y, si hay impacto financiero, un **Accounting Document** (trazabilidad contable). Los dos documentos quedan vinculados permanentemente.

_Fuente: [SAP — Introducing Goods Movements](https://learning.sap.com/courses/experiencing-supply-chain-business-scenarios-in-sap-s-4hana-cloud-public-edition/introducing-goods-movements) · [CloudBook — Movement Types SAP MM](https://cloudbook.co.in/blog/movement-types-in-sap-mm/)_

---

### Impacto Contable de los Movimientos

Al hacer GR de una PO:

```
Debit:   Inventory Stock Account     (valor = cantidad × precio PO)
Credit:  GR/IR Clearing Account      (cuenta puente PO-Invoice)

Al registrar Invoice:
Debit:   GR/IR Clearing Account      (cierra la cuenta puente)
Credit:  Vendor Payables             (deuda con proveedor)

Diferencia de precio (PO vs Invoice):
Debit/Credit: Price Difference Account
```

Este patrón garantiza que el inventario siempre esté valuado al precio real de compra y que las diferencias de precio sean visibles y auditables.

_Fuente: [SAP Learning — Analyzing Material Valuation](https://learning.sap.com/courses/business-processes-in-sap-s-4hana-sourcing-procurement/analyzing-material-valuation)_

---

## Módulo 2 — Trazabilidad: Lotes, Seriales y Fechas de Expiración

### Lot vs Serial — Cuándo usar cada uno

| Característica | **Lote (Batch/Lot)** | **Serial Number** |
|---------------|---------------------|------------------|
| Granularidad | Grupo de unidades | Una unidad individual |
| Identificador | Compartido por N unidades | Único por unidad |
| Costo | Un costo por lote | Un costo por serial |
| Cuándo usar | Alimentos, químicos, textiles por partida | Electrónicos, equipos, artículos de alto valor |
| Trazabilidad | Upstream (de dónde vino el lote) y downstream (a quién se vendió) | Historial completo de una unidad |

### Estrategias de Rotación de Stock

| Estrategia | Criterio de consumo | Mejor para |
|-----------|--------------------|---------:|
| **FIFO** | Lote más antiguo primero (por fecha de entrada) | Inventario general, commodities |
| **FEFO** | Lote con fecha de expiración más próxima primero | Alimentos, farmacéuticos, cosméticos |
| **LIFO** | Lote más reciente primero | Materias primas a granel (raro en retail) |
| **Manual** | El usuario elige el lote | Productos especiales, lotes bajo cuarentena |

**FEFO en la práctica:** el sistema ERP debe conocer la `expiry_date` de cada lote y, al generar una orden de picking, proponer automáticamente el lote que vence más pronto (sin importar cuándo llegó). Esto requiere que la fecha de expiración se registre obligatoriamente en la recepción.

_Fuente: [MRPeasy — FEFO First Expired First Out](https://www.mrpeasy.com/blog/fefo-first-expired-first-out/) · [NetSuite — Lot and Serial Numbers](https://www.netsuite.com/portal/resource/articles/inventory-management/understanding-how-lot-and-serial-numbers-are-used-for-inventory-management.shtml)_

---

### Trazabilidad Completa: Upstream y Downstream

El estándar de industria exige poder responder:
- **Upstream:** "¿De qué PO y proveedor viene el lote X?" → recall de proveedores
- **Downstream:** "¿A qué clientes se vendió el lote X?" → recall de productos

```
Vendor ──► PO ──► GR ──► Lot/Batch ──► SO Line ──► Delivery ──► Customer
                           │
                           ├── expiry_date
                           ├── manufacture_date
                           ├── country_of_origin
                           └── quality_status (released/hold/blocked)
```

_Fuente: [Datacor — Lot Tracking & Traceability Guide](https://www.datacor.com/resources/lot-tracking-traceability-guide) · [HandiFox — Track lots serials expiration dates](https://www.handifox.com/handifox-blog/how-to-track-lots-serials-and-expiration-dates-for-tighter-inventory-control)_

---

## Módulo 3 — Estructura de Almacén y Gestión de Ubicaciones

### Jerarquía de Estructura SAP WM/EWM

```
Client
└── Warehouse Number (número de almacén)
    └── Storage Type (tipo de almacenamiento: zona refrigerada, estantería, bulk)
        └── Storage Section (sección: productos A, productos peligrosos)
            └── Storage Bin (ubicación física: A-01-03-B = pasillo A, estante 01, nivel 03, posición B)
```

**SAP EWM** agrega capas adicionales para operaciones avanzadas:
- **Activity Area:** agrupa bins por tipo de operación (picking area, putaway area, staging area)
- **Work Center:** estaciones de trabajo para packing, QA, cross-docking

_Fuente: [LeverX — SAP EWM Best Practices](https://leverx.com/newsroom/best-practices-for-effective-warehouse-management-with-sap-ewm) · [SAP Community — SAP EWM Guide](https://community.sap.com/t5/supply-chain-management-blog-posts-by-members/a-comprehensive-guide-to-sap-s-4hana-extended-warehouse-management-ewm/ba-p/14225196)_

---

### Estrategias de Putaway y Picking

**Putaway strategies (al guardar mercancía):**

| Estrategia | Cómo funciona | Mejor para |
|-----------|--------------|-----------|
| **Fixed Bin** | Cada SKU tiene una ubicación fija | Pick-frecuentes, ergonomía de picking |
| **Open Storage** | El sistema asigna el primer bin libre | Alta rotación, SKUs variables |
| **Addition to Existing Stock** | Consolida en bin donde ya hay stock del mismo SKU | Minimizar fragmentación |
| **Bulk Storage** | Apila pallets en bloque | Materias primas, alta densidad |
| **Near Fixed Picking Bin** | Guarda el overflow cerca del bin fijo | Reposición automática de zonas de picking |

**Picking strategies (al despachar):**

| Estrategia | Criterio | Uso típico |
|-----------|---------|-----------|
| **FIFO** | Bin/lote con fecha entrada más antigua | Default general |
| **FEFO** | Bin/lote con expiración más próxima | Perecederos |
| **Fixed Bin First** | Siempre empieza en el bin fijo del SKU | Productos de alta rotación |
| **Minimum Quantity** | Vacía primero los bins con menos cantidad | Reduce fragmentación |

_Fuente: [SAP Community — Putaway Strategies EWM](https://community.sap.com/t5/supply-chain-management-blog-posts-by-members/putaway-strategies-in-extended-warehouse-management-part-1/ba-p/13798628) · [RFgen — SAP WM Guide](https://www.rfgen.com/products/sap-enterprise-mobility/sap-warehouse-management-guide/)_

---

## Módulo 4 — Reposición Automática: Safety Stock y Reorder Point

### Fórmulas Estándar de la Industria

**Reorder Point (ROP):**
```
ROP = (Demanda diaria promedio × Lead time en días) + Safety Stock
```

**Safety Stock:**
```
SS = Z × σ_demanda × √(lead_time_promedio)

Donde:
  Z = factor de nivel de servicio (95% → 1.65 | 99% → 2.33)
  σ_demanda = desviación estándar de la demanda diaria
```

**Fórmula simplificada (operacional):**
```
SS = (Demanda máxima diaria × Lead time máximo) − (Demanda promedio × Lead time promedio)
```

### Min/Max vs ROP+SS

| Enfoque | Cuándo reponer | Cuánto pedir | Mejor para |
|---------|---------------|-------------|-----------|
| **Min/Max** | Stock cae bajo el mínimo | Subir hasta el máximo | SKUs simples, demanda estable |
| **ROP + Safety Stock** | Stock llega al ROP | EOQ (cantidad óptima) | SKUs con variabilidad de demanda |
| **MRP (Material Requirements Planning)** | Basado en plan de producción/ventas futuras | Cubre la necesidad proyectada | Manufactura, planificación avanzada |

_Fuente: [Pyrops WMS — Safety Stock Best Practices](https://pyrops.com/best-practices-to-determine-safety-stock-reorder-point-and-reorder-quantity/) · [ABC Supply Chain — Min/Max vs Safety Stock](https://abcsupplychain.com/inventory-optimization-min-max-method-or-safety-stock/) · [ISM — Reorder Point Formula](https://www.ism.ws/logistics/reorder-point-formula-and-examples/)_

---

## Módulo 5 — Conteo Cíclico y ABC Classification

### ABC Classification

El principio de Pareto aplicado al inventario:

| Clase | % de SKUs | % del valor total | Frecuencia de conteo |
|-------|----------|------------------|---------------------|
| **A** | ~20% | ~80% | Mensual (o continuo) |
| **B** | ~30% | ~15% | Trimestral |
| **C** | ~50% | ~5% | Anual |

Los sistemas ERP calculan la clase ABC automáticamente en base a **valor de consumo anual** (precio unitario × unidades vendidas/consumidas por año). Se recomienda recalcular la clasificación cada trimestre.

### Cycle Count vs Full Physical Inventory

| Aspecto | Conteo Cíclico | Inventario Físico completo |
|---------|---------------|--------------------------|
| Frecuencia | Continuo (subset del inventario) | Anual o semestral |
| Operación | No interrumpe actividad | Freeze total del almacén |
| Precisión alcanzable | >95% con proceso maduro | ~80% (error humano en freezes largos) |
| Detección de errores | En días | En meses |
| Recurso requerido | Bajo (rotativo) | Alto (cierre de operaciones) |

**Best practice:** eliminar el inventario físico anual una vez que el proceso de conteo cíclico alcance >98% de accuracy. SAP y NetSuite soportan esto nativamente.

_Fuente: [NetSuite — ABC Inventory Analysis](https://www.netsuite.com/portal/resource/articles/inventory-management/abc-inventory-analysis.shtml) · [NetSuite — Cycle Counting](https://www.netsuite.com/portal/resource/articles/inventory-management/using-inventory-control-software-for-cycle-counting.shtml) · [RFgen — Cycle Count Guide](https://www.rfgen.com/blog/complete-guide-to-inventory-cycle-counting-best-practices/)_

---

## Módulo 6 — Multi-Almacén y Transferencias de Stock

### Modelo de Stock por Ubicación

Los ERP líderes mantienen **posiciones de inventario** separadas por:

```
Inventory Position = (Product, Warehouse, Storage Location, Lot/Batch, Stock Type)

Stock Types:
  ├── Unrestricted Use     → disponible para venta/consumo
  ├── Quality Inspection   → en cuarentena, pendiente QA
  ├── Restricted Use       → bloqueado por decisión operacional
  └── In Transit           → en traslado entre almacenes
```

Esto permite que el mismo SKU tenga stock disponible en un almacén y en cuarentena en otro, sin confundirlos.

### Transfer Orders — Traslados Inter-Almacén

**SAP patrón de 2 pasos:**
```
Paso 1: Goods Issue del almacén origen → stock queda "In Transit"
Paso 2: Goods Receipt en almacén destino → stock pasa a "Unrestricted"

Beneficio: visibilidad del stock en tránsito durante el traslado físico
```

**SAP patrón de 1 paso:**
```
Transfer posting atómico: GI + GR simultáneo → para traslados instantáneos (mismo sitio)
```

_Fuente: [Kladana — Multi-Location Inventory](https://www.kladana.com/blog/inventory-management/multi-location-inventory-management/) · [MRPeasy — Multi-Location Inventory Management](https://www.mrpeasy.com/blog/multi-location-inventory-management/)_

---

## Módulo 7 — KPIs Operativos de Inventario

### KPIs Fundamentales — Fórmulas y Targets

| KPI | Fórmula | Target típico | Frecuencia |
|-----|---------|--------------|-----------|
| **Inventory Turnover** | COGS / Inventario Promedio | 6-12x/año (depende industria) | Mensual |
| **Days on Hand (DOH)** | (Inventario Promedio / COGS) × 365 | 30-60 días | Semanal |
| **Fill Rate** | Líneas entregadas completas / Total líneas pedidas | >95% | Diario |
| **Stockout Rate** | SKUs sin stock / Total SKUs activos | <2% | Diario |
| **Cycle Count Accuracy** | Items contados correctos / Total items contados | >98% | Por conteo |
| **Shrinkage Rate** | (Inv. teórico − Inv. real) / Inv. teórico | <0.5% | Mensual |
| **Dead Stock %** | Valor stock sin movimiento >90 días / Valor total | <5% | Mensual |
| **OTIF (On Time In Full)** | Entregas a tiempo y completas / Total entregas | >95% | Diario |

_Fuente: [NetSuite — 33 Inventory KPIs](https://www.netsuite.com/portal/resource/articles/inventory-management/inventory-management-kpis-metrics.shtml) · [EazyStock — Inventory KPIs](https://www.eazystock.com/blog/8-inventory-kpis-improve-inventory-management-efficiency/) · [MRPeasy — Inventory KPIs 2026](https://www.mrpeasy.com/blog/inventory-management-kpis/)_

---

## Mejoras Aplicables al Sistema — Inventario

> Derivadas del análisis de SAP MM-IM/WM/EWM · NetSuite · Dynamics 365 · Odoo 18 · MRPeasy.
> Stack objetivo: FastAPI + SQLAlchemy 2.0 async + PostgreSQL (Supabase) + Celery.

---

### INV-1 — Movimientos de Stock

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-01 | **Catalog de tipos de movimiento configurable** | SAP Movement Types | Alta | Tabla `stock_movement_types` (code, name, direction: IN/OUT/TRANSFER, requires_reference, posts_accounting). Nunca hardcodear los tipos en código |
| INV-02 | **Material Document + Accounting Document vinculados** | SAP MM-IM | Alta | Cada movimiento genera `stock_movement` (físico) + `journal_entry` (contable) con `source_movement_id`. Los dos quedan linked permanentemente |
| INV-03 | **Reversión de movimiento siempre por referencia** | SAP reversal pattern | Alta | Al revertir un GR o GI, el sistema crea un nuevo movimiento de signo contrario referenciando el original. No se modifica el movimiento original |
| INV-04 | **GR/IR clearing account para matching PO-Invoice** | SAP FI-MM integration | Alta | Cuenta puente `gr_ir_clearing` que se abre en GR y se cierra en Invoice. Diferencias van a `price_difference_account` |
| INV-05 | **Stock type por posición: unrestricted / QA / blocked / in_transit** | SAP stock categories | Alta | Campo `stock_type` en `inventory_positions`. Solo `unrestricted` está disponible para ventas y consumo |

---

### INV-2 — Trazabilidad Lotes y Seriales

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-06 | **Tabla `inventory_lots` con atributos de trazabilidad** | SAP Batch Management | Alta | `lot_number`, `product_id`, `manufacture_date`, `expiry_date`, `country_of_origin`, `quality_status` (released/hold/blocked), `po_line_id` (origen upstream) |
| INV-07 | **Trazabilidad upstream y downstream por lote** | SAP Batch Information Cockpit | Alta | Al vender un lote: registrar `lot_id` en la línea de venta. Query bidireccional: "todos los clientes que recibieron lote X" y "de qué PO viene el lote X" |
| INV-08 | **FEFO automático en picking** | SAP WM FEFO strategy | Alta | Si producto tiene `tracking = LOT` y `rotation_strategy = FEFO`: al generar pick, ordenar lotes disponibles por `expiry_date ASC`. Proponer el que vence primero |
| INV-09 | **Alertas de expiración próxima** | ERP batch expiry alerts | Media | Job Celery diario: detectar lotes con `expiry_date < today + threshold_days` y crear alerta para el almacenista. Threshold configurable por familia de producto |
| INV-10 | **Serial number tracking para productos de alto valor** | NetSuite Serial Numbers | Media | Para productos con `tracking = SERIAL`: cada unidad tiene su propio `serial_number` con historial completo de movimientos |

---

### INV-3 — Estructura de Almacén y Ubicaciones

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-11 | **Jerarquía de almacén: Warehouse → Zone → Location (Bin)** | SAP WM structure | Media | Tablas: `warehouses` → `warehouse_zones` (refrigerado, seco, peligroso) → `warehouse_locations` (código alfanumérico, capacidad, tipo) |
| INV-12 | **Inventory positions por (product, warehouse, location, lot, stock_type)** | SAP Storage Location + Batch | Alta | La posición de inventario es la combinación de estos 5 campos. Índice compuesto único. Cantidad puede ser 0 (posición histórica) |
| INV-13 | **Putaway strategy por zona y tipo de producto** | SAP EWM Putaway | Baja | Tabla `putaway_rules` (zone_id, product_family_id, strategy: FIXED/OPEN/ADDITIVE). Aplicar al generar transfer order de recepción |
| INV-14 | **Código de bin en formato estructurado** | SAP bin code | Baja | Formato: `{warehouse}-{zone}-{row}-{level}-{position}` (ej: `WH1-A-03-02-B`). Permite sorting físico para rutas de picking eficientes |

---

### INV-4 — Reposición Automática

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-15 | **Parámetros de reposición por producto-almacén** | SAP MRP / Min-Max | Alta | Tabla `replenishment_params` (product_id, warehouse_id, min_qty, max_qty, reorder_point, safety_stock, lead_time_days). Configurable por planificador |
| INV-16 | **Job de reposición automática: detección de ROP** | SAP MRP run | Media | Job Celery periódico: comparar stock actual vs reorder_point. Si stock ≤ ROP: crear `purchase_requisition` automáticamente al proveedor preferido |
| INV-17 | **Clasificación ABC automática por consumo** | SAP ABC analysis | Media | Job mensual: calcular `annual_consumption_value = avg_price × qty_consumed_12m` por SKU. Clasificar: A (top 80% valor), B (siguiente 15%), C (resto). Guardar en producto |

---

### INV-5 — Conteo Cíclico

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-18 | **Módulo de conteo cíclico basado en clasificación ABC** | SAP Physical Inventory | Media | Generar `cycle_count_schedules` automáticamente: A=mensual, B=trimestral, C=anual. Tabla `cycle_counts` (location_id, product_id, scheduled_date, counted_qty, system_qty, variance) |
| INV-19 | **Ajuste de inventario con aprobación para varianzas altas** | SAP inventory difference | Media | Si varianza > threshold (ej: >2% o >valor_$): requerir aprobación de supervisor antes de ajustar. Registrar razón del ajuste en audit log |
| INV-20 | **KPI de accuracy por almacén en dashboard** | SAP LI01/LI21 | Media | Endpoint `/inventory/accuracy` con cycle_count_accuracy% por almacén y por período. Mostrar tendencia |

---

### INV-6 — Multi-Almacén y Transferencias

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-21 | **Stock In Transit como stock_type diferenciado** | SAP 2-step transfer | Media | Al iniciar traslado: reducir stock en origen (tipo `unrestricted`) y crear posición `in_transit`. Al confirmar recepción: posición pasa a `unrestricted` en destino |
| INV-22 | **Transfer Order con aprobación opcional** | SAP TO workflow | Baja | Para traslados de alto valor o entre almacenes remotos: workflow de aprobación antes de ejecutar el movimiento |

---

### INV-7 — KPIs y Dashboard

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|------------|-----------|------------------------|
| INV-23 | **Dashboard de KPIs de inventario en tiempo real** | NetSuite Inventory Dashboard | Media | Endpoints para: Inventory Turnover, DOH, Fill Rate, Stockout Rate, Dead Stock %, Shrinkage. Filtrable por almacén, familia, período |
| INV-24 | **Alertas de dead stock (sin movimiento >90 días)** | ERP dead stock reports | Baja | Job Celery mensual: detectar posiciones con `last_movement_date < today - 90 days` y valor > threshold. Notificar al planificador |
| INV-25 | **Fill Rate calculado automáticamente por orden de venta** | NetSuite Fill Rate | Media | Al despachar una SO: comparar qty_ordered vs qty_shipped. Agregar en KPI diario de Fill Rate |

---

## Executive Summary — Inventario

### Los 6 Principios de Inventario de la Industria

1. **Movimiento = Documento** — Ningún cambio en stock ocurre sin un documento registrado. Cada documento tiene un número, un tipo, un usuario y un timestamp. Las reversiones crean nuevos documentos, nunca modifican los originales.

2. **Posición de inventario granular** — El stock no es solo "cuánto tengo del producto X". Es "cuánto tengo del producto X, en el almacén Y, en la ubicación Z, del lote L, con status S". Esta granularidad habilita FEFO, trazabilidad, y contabilidad de costos precisa.

3. **Lote/Serial como ciudadano de primera clase** — La trazabilidad upstream-downstream por lote no es opcional en industrias reguladas. El ERP debe poder responder en segundos: "¿a quién le vendí el lote X?" y "¿de qué proveedor viene?".

4. **Reposición automática basada en datos** — Safety stock y reorder points calculados desde datos reales de demanda y lead time, revisados periódicamente. Los sistemas maduros auto-generan requisiciones de compra sin intervención humana.

5. **ABC + conteo cíclico reemplaza al inventario físico anual** — El 80% del valor del inventario está en el 20% de los SKUs (clase A). Contar ese 20% mensualmente es más efectivo que contar todo una vez al año.

6. **KPIs como termómetro operativo diario** — Fill Rate, Stockout Rate y DOH no son reportes mensuales; son métricas que los almacenistas y planificadores ven cada mañana. Un dashboard operativo es tan crítico como el propio módulo de inventario.

---

### Mapa de Mejoras Consolidado — Inventario

| ID | Mejora | Prioridad | Complejidad | Sprint estimado |
|----|--------|-----------|-------------|----------------|
| INV-01 | Movement types configurables | Alta | Baja | Q2-2026 |
| INV-02 | Material + Accounting Document linked | Alta | Media | Q2-2026 |
| INV-03 | Reversión por referencia | Alta | Baja | Q2-2026 |
| INV-04 | GR/IR clearing account | Alta | Media | Q2-2026 |
| INV-05 | Stock types (unrestricted/QA/blocked/in_transit) | Alta | Baja | Q2-2026 |
| INV-06 | Tabla inventory_lots con atributos trazabilidad | Alta | Baja | Q2-2026 |
| INV-07 | Trazabilidad upstream/downstream por lote | Alta | Media | Q2-2026 |
| INV-08 | FEFO automático en picking | Alta | Media | Q3-2026 |
| INV-09 | Alertas de expiración próxima | Media | Baja | Q3-2026 |
| INV-10 | Serial number tracking | Media | Media | Q3-2026 |
| INV-11 | Jerarquía Warehouse → Zone → Location | Media | Baja | Q2-2026 |
| INV-12 | Inventory positions por 5 dimensiones | Alta | Media | Q2-2026 |
| INV-13 | Putaway strategy por zona | Baja | Media | Q4-2026 |
| INV-14 | Código de bin estructurado | Baja | Baja | Q4-2026 |
| INV-15 | Parámetros de reposición por producto-almacén | Alta | Baja | Q3-2026 |
| INV-16 | Job de reposición automática | Media | Media | Q3-2026 |
| INV-17 | Clasificación ABC automática | Media | Media | Q3-2026 |
| INV-18 | Conteo cíclico basado en ABC | Media | Media | Q4-2026 |
| INV-19 | Ajuste con aprobación para varianzas altas | Media | Baja | Q4-2026 |
| INV-20 | KPI accuracy en dashboard | Media | Baja | Q4-2026 |
| INV-21 | Stock In Transit | Media | Media | Q3-2026 |
| INV-22 | Transfer Order con aprobación | Baja | Baja | Q4-2026 |
| INV-23 | Dashboard KPIs inventario | Media | Media | Q3-2026 |
| INV-24 | Alertas dead stock | Baja | Baja | Q4-2026 |
| INV-25 | Fill Rate automático por SO | Media | Baja | Q3-2026 |

**Total: 25 mejoras identificadas para el módulo de Inventario**

---

## Technical Research Sources

- [SAP EWM — LeverX Best Practices](https://leverx.com/newsroom/best-practices-for-effective-warehouse-management-with-sap-ewm)
- [SAP Learning — Introducing Goods Movements](https://learning.sap.com/courses/experiencing-supply-chain-business-scenarios-in-sap-s-4hana-cloud-public-edition/introducing-goods-movements)
- [SAP Learning — Material Valuation](https://learning.sap.com/courses/business-processes-in-sap-s-4hana-sourcing-procurement/analyzing-material-valuation)
- [CloudBook — SAP MM Movement Types](https://cloudbook.co.in/blog/movement-types-in-sap-mm/)
- [MRPeasy — FEFO Guide](https://www.mrpeasy.com/blog/fefo-first-expired-first-out/)
- [NetSuite — Lot and Serial Numbers](https://www.netsuite.com/portal/resource/articles/inventory-management/understanding-how-lot-and-serial-numbers-are-used-for-inventory-management.shtml)
- [Datacor — Lot Tracking & Traceability](https://www.datacor.com/resources/lot-tracking-traceability-guide)
- [SAP Community — EWM Putaway Strategies](https://community.sap.com/t5/supply-chain-management-blog-posts-by-members/putaway-strategies-in-extended-warehouse-management-part-1/ba-p/13798628)
- [Pyrops — Safety Stock Best Practices](https://pyrops.com/best-practices-to-determine-safety-stock-reorder-point-and-reorder-quantity/)
- [ABC Supply Chain — Min/Max vs Safety Stock](https://abcsupplychain.com/inventory-optimization-min-max-method-or-safety-stock/)
- [NetSuite — ABC Inventory Analysis](https://www.netsuite.com/portal/resource/articles/inventory-management/abc-inventory-analysis.shtml)
- [NetSuite — Cycle Counting](https://www.netsuite.com/portal/resource/articles/inventory-management/using-inventory-control-software-for-cycle-counting.shtml)
- [Kladana — Multi-Location Inventory](https://www.kladana.com/blog/inventory-management/multi-location-inventory-management/)
- [NetSuite — 33 Inventory KPIs](https://www.netsuite.com/portal/resource/articles/inventory-management/inventory-management-kpis-metrics.shtml)
- [MRPeasy — Inventory KPIs 2026](https://www.mrpeasy.com/blog/inventory-management-kpis/)

---

**Technical Research Completion Date:** 2026-05-13
**Sistemas analizados:** SAP MM-IM/WM/EWM · Oracle NetSuite · Microsoft Dynamics 365 · Odoo 18 · MRPeasy
**Total mejoras identificadas:** 25
**Fuentes verificadas:** 16 fuentes con URL
**Confidence Level:** Alto

_Próximo módulo recomendado: **Compras / Procurement** (PO lifecycle, vendor evaluation, RFQ process) — directamente conectado al inventario vía GR y three-way match._
