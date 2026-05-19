---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'ERP Procurement / Compras — mejores prácticas de la industria'
research_goals: 'Identificar mejores prácticas del ciclo P2P (Procure-to-Pay) y documentar mejoras aplicables a br-mt-ecommerce'
user_name: 'psierra'
date: '2026-05-13'
web_research_enabled: true
source_verification: true
---

# Research Report: ERP Procurement / Compras — Mejores Prácticas

**Fecha:** 2026-05-13
**Autor:** psierra
**Flujo:** Maestros ✅ → Inventario ✅ → **Compras** → Pricing → Ventas → Billing → Finanzas

---

## Research Overview

Investigación técnica del ciclo **Procure-to-Pay (P2P)** en SAP MM, Oracle NetSuite, Microsoft Dynamics 365 y Odoo. Cubre desde la solicitud de compra hasta el pago al proveedor, incluyendo tipos de orden, matriz de aprobación, determinación de fuente, verificación de facturas y KPIs de procurement. Encadena directamente con [Inventario](./technical-erp-inventario-mejores-practicas-research-2026-05-13.md) (vía Goods Receipt) y con [Maestros](./technical-erp-master-data-mejores-practicas-industria-research-2026-05-13.md) (Vendor Master + Pricing).

---

## El Ciclo P2P — Flujo Completo

```
Necesidad detectada
      │
      ▼
Purchase Requisition (PR)  ──► Approval Workflow (matriz de autorizaciones)
      │
      ▼
Source Determination        ──► Info Record / Source List / Quota / RFQ
      │
      ▼
Purchase Order (PO)         ──► Confirmación del proveedor
      │
      ▼
Goods Receipt (GR)          ──► Actualiza Inventario + abre GR/IR clearing
      │
      ▼
Invoice Verification (IV)   ──► Three-Way Match: PO ↔ GR ↔ Invoice
      │                              Si excede tolerancia → Payment Block
      ▼
Payment (F110)              ──► Cierra GR/IR + registra pago en banco
```

_Fuente: [GTR Academy — SAP P2P Process](https://gtracademy.org/procure-to-pay-process-in-sap-mm/) · [SAP — What is Procure-to-Pay](https://www.sap.com/resources/what-is-procure-to-pay) · [Stampli — SAP P2P Guide](https://www.stampli.com/blog/all/procure-to-pay-sap-process/)_

---

## Módulo 1 — Purchase Requisition (PR)

### Qué es y por qué importa

La PR es el punto de partida de todo procurement. Es una solicitud interna (no va al proveedor) que debe ser aprobada antes de convertirse en PO. Genera visibilidad y control de gasto antes de comprometer dinero.

**Atributos clave de una PR:**
- Material / servicio solicitado
- Cantidad y unidad de medida
- Fecha requerida
- Centro de costo / proyecto que asume el gasto
- Fuente sugerida (proveedor preferido)
- Solicitante + aprobadores requeridos

**Best practices de la industria:**
- Una PR por necesidad (no agrupar manualmente — el sistema lo hace al convertir a PO)
- Campos obligatorios mínimos: material, cantidad, fecha, centro de costo
- Conversión automática a PO si la PR cumple criterios predefinidos (auto-PO)

_Fuente: [Stampli — Purchase Requisition Best Practices](https://www.stampli.com/blog/accounts-payable/purchase-requisition-best-practices/)_

---

## Módulo 2 — Matriz de Aprobación (Authorization Matrix)

### El Patrón Estándar de la Industria

Los sistemas líderes implementan aprobación en **tres ejes simultáneos**:

| Eje | Criterio | Ejemplo |
|-----|---------|---------|
| **Monto** | Límite de aprobación por rol | <$1k: auto-aprobado · $1k-$10k: jefe depto · >$10k: CFO |
| **Categoría** | Tipo de compra | IT Hardware → aprobación IT-Security adicional |
| **Riesgo** | Factores especiales | Proveedor nuevo → aprobación Purchasing especial |

**Benchmark de industria (top performers 2025):** tiempo de requisición a PO < 4.2 horas hábiles con routing electrónico.

**Escalación automática:** si un aprobador no responde en N horas, el sistema escala al siguiente nivel. Sin escalación, las PRs quedan bloqueadas indefinidamente.

```
PR creada
    │
    ├── Monto < $1,000 ──────────────────────────────► Auto-aprobado → PO
    │
    ├── $1,000 - $10,000 ──► Jefe de Departamento
    │                              │ aprueba → PO
    │                              │ rechaza → PR cancelada con razón
    │                              │ sin respuesta 24h → escala a Director
    │
    └── > $10,000 ──────────► Director → CFO → PO
```

_Fuente: [Tipalti — Approval Matrix](https://tipalti.com/resources/learn/approval-matrix/) · [GEP — PO Approval Process 2026](https://www.gep.com/blog/strategy/purchase-order-approval-process-guide) · [ApprovIt — PO Approval Workflow 2025](https://approveit.today/blog/purchase-order-approval-workflow-with-ai-rules-thresholds-templates-(2025))_

---

## Módulo 3 — Tipos de Orden de Compra

### Los 4 tipos de PO en SAP (patrón de industria)

| Tipo | Cuándo usar | Característica clave |
|------|------------|---------------------|
| **Standard PO** | Compra puntual con cantidad y precio definidos | Un PO = una entrega específica |
| **Blanket / Framework PO** | Monto abierto con proveedor por período | Se consume contra el tope; sin cantidad fija por línea |
| **Contract (Value/Quantity)** | Acuerdo marco a largo plazo | Genera release orders (POs hijo) contra el contrato |
| **Scheduling Agreement** | Entregas recurrentes con fechas predefinidas | Una línea = múltiples schedule lines con fecha+cantidad |

**Cuándo usar cada uno en br-mt:**
- Proveedor ocasional → **Standard PO**
- Proveedor de servicios (mantenimiento, limpieza) → **Blanket PO** (monto abierto mensual)
- Proveedor estratégico con volumen negociado → **Contract** + release orders
- Proveedor con entregas JIT programadas → **Scheduling Agreement**

_Fuente: [SAP Learning — Working with Contracts](https://learning.sap.com/courses/purchasing-in-sap-s-4hana/working-with-contracts) · [CloudBook — Scheduling Agreements SAP MM](https://cloudbook.co.in/blog/scheduling-agreements-in-sap-mm-a-comprehensive-guide/) · [ProcureDesk — Blanket PO](https://www.procuredesk.com/blanket-purchase-order/)_

---

## Módulo 4 — Source Determination (Determinación de Fuente)

### Jerarquía de determinación en SAP

Cuando se necesita comprar un material, el sistema busca el proveedor en este orden de prioridad:

```
1. Quota Arrangement   → Si hay cuota de reparto entre proveedores
        │ no encontrado
        ▼
2. Source List         → Proveedores aprobados para este material/planta/período
        │ no encontrado
        ▼
3. Outline Agreement   → Contratos o scheduling agreements vigentes
        │ no encontrado
        ▼
4. Purchasing Info Record (PIR) → Precio y condiciones históricas
```

### Purchasing Info Record (PIR) — El "precio acordado"

El PIR vincula un proveedor con un material específico y almacena:
- Precio de compra vigente (con fecha de validez)
- Lead time del proveedor
- Cantidad mínima de orden (MOQ)
- Tolerancia de entrega (over/under delivery)
- Datos de aduana (para importaciones)

**Regla de oro:** si existe un PIR vigente para la combinación vendor-material, el sistema propone el precio automáticamente al crear el PO. No hay que introducirlo manualmente.

### Source List — Lista de proveedores aprobados

Permite definir, por material y planta, qué proveedores están **aprobados** y cuál es el **preferido (fixed)**. Si se declara obligatoria, solo se puede comprar a proveedores en la Source List → control de gasto maverick.

_Fuente: [TutorialsPoint — SAP MM Source List](https://www.tutorialspoint.com/sap_mm/sap_mm_source_determination_list.htm) · [SAP Learning — Source Lists S/4HANA](https://learning.sap.com/learning-journeys/exploring-sourcing-in-s-4hana/introducing-source-lists-sap-s-4hana)_

---

## Módulo 5 — RFQ y Evaluación de Proveedores

### El Proceso de Cotización (RFQ)

```
RFQ creada ──► Enviada a N proveedores
                      │
                      ▼
              Proveedores responden con cotizaciones
                      │
                      ▼
              Comparativa de precios (price comparison sheet)
              + criterios adicionales (calidad, tiempo de entrega, condiciones)
                      │
                      ▼
              Proveedor seleccionado → RFQ se convierte en PO
              Proveedores rechazados → Notificación de rechazo (buenas prácticas)
```

**RFQ Operacional vs Estratégico:**
- **Operacional:** compras menores, solo comparación de precio, proceso rápido
- **Estratégico:** compras grandes, scoring multi-criterio (precio 40% + calidad 30% + tiempo entrega 20% + condiciones pago 10%), evaluación formal de proveedores

_Fuente: [Futura Solutions — Operational vs Strategic RFQ](https://www.futura-solutions.de/en/blog/operational-strategic-rfq/) · [ERPGreat — What is RFQ](https://www.erpgreat.com/materials/what-is-request-for-quotation.htm)_

---

## Módulo 6 — Invoice Verification y Payment Blocks

### Tolerance Keys — El Sistema de Tolerancias SAP

El sistema de verificación de facturas en SAP usa **tolerance keys** para decidir automáticamente si bloquear o aprobar una factura con discrepancias:

| Tolerance Key | Qué verifica | Acción si excede |
|--------------|-------------|-----------------|
| **AN** | Diferencia de monto por ítem | Bloquea pago |
| **AP** | Diferencia porcentual de precio | Bloquea pago |
| **BD** | Diferencia de monto en el balance | Bloquea pago |
| **BR** | Diferencia de cantidad recibida | Bloquea pago |
| **BW** | Diferencia de fecha de entrega | Warning (no bloquea) |

**Configuración típica:**
```
AN: ±$50 absoluto → dentro: auto-aprueba; fuera: bloquea
AP: ±2% de precio → dentro: auto-aprueba; fuera: bloquea
BR: ±1 unidad → dentro: auto-aprueba; fuera: bloquea
```

**Stochastic block:** algunos AP teams configuran un bloqueo aleatorio de X% de las facturas para revisión spot check, independiente de las tolerancias.

_Fuente: [SAP Community — Invoice Tolerance Keys](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/invoice-tolerance-keys-an-insight-part-1/ba-p/13085884) · [Mohan Ranga — Payment Blocks](https://www.mohanranga.com/blogs/finance/payment-blocks)_

---

## Módulo 7 — KPIs de Procurement

### KPIs Fundamentales

| KPI | Fórmula | Target top performer | Frecuencia |
|-----|---------|---------------------|-----------|
| **PO Cycle Time** | Fecha PO − Fecha PR | < 4.2 horas hábiles | Diario |
| **Vendor On-Time Delivery** | GRs en fecha / Total GRs | > 95% | Semanal |
| **Invoice Processing Time** | Fecha pago − Fecha factura recibida | < 5 días hábiles | Mensual |
| **Spend Under Management** | Gasto via PO aprobado / Gasto total | > 80% | Mensual |
| **PO Accuracy Rate** | POs sin corrección / Total POs | > 98% | Mensual |
| **Maverick Spending** | Compras sin PO / Gasto total | < 5% | Mensual |
| **Vendor Fill Rate** | Líneas entregadas completas / Líneas PO | > 95% | Semanal |
| **Cost Savings** | Precio negociado vs precio de mercado | > 8% ahorro anual | Trimestral |

_Fuente: [NetSuite — 35 Procurement KPIs](https://www.netsuite.com/portal/resource/articles/erp/procurement-kpis.shtml) · [Vroozi — 25 Procurement KPIs 2025](https://www.vroozi.com/blog/procurement-kpis-25-essential-metrics-to-track-in-2025/)_

---

## Mejoras Aplicables al Sistema — Compras (P2P)

> Derivadas del análisis de SAP MM, NetSuite, Dynamics 365, Odoo.
> Stack objetivo: FastAPI + SQLAlchemy + PostgreSQL + Celery.
> Encadena con: Maestros (Vendor Master) → Inventario (GR) → Billing (Invoice → Payment).

---

### PRC-1 — Purchase Requisition

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-01 | **Módulo de Purchase Requisition (PR) como entidad propia** | SAP ME51N | Alta | Tabla `purchase_requisitions` (requester_id, product_id, qty, uom, required_date, cost_center_id, suggested_vendor_id, status). Separada del PO |
| PRC-02 | **Status lifecycle de PR: draft → pending_approval → approved → converted / rejected / cancelled** | SAP PR Release | Alta | Transiciones controladas. Solo PRs `approved` pueden convertirse a PO |
| PRC-03 | **Auto-conversión PR → PO para compras bajo umbral** | SAP auto-PO | Media | Si monto < threshold Y proveedor está en Source List → crear PO automáticamente sin aprobación manual |

---

### PRC-2 — Matriz de Aprobación

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-04 | **Tabla de aprobación configurable por monto y categoría** | Industry approval matrix | Alta | Tabla `approval_rules` (document_type, min_amount, max_amount, category_id, approver_role, approver_user_id). N niveles configurables sin cambiar código |
| PRC-05 | **Escalación automática por timeout** | SAP workflow escalation | Alta | Si aprobador no responde en `timeout_hours`: escalar al siguiente nivel. Job Celery Beat periódico que detecta aprobaciones vencidas |
| PRC-06 | **Notificaciones in-app + email al aprobador** | SAP workflow notifications | Media | Al crear PR: notificar al aprobador. Al aprobar/rechazar: notificar al solicitante con razón |
| PRC-07 | **Log de decisiones de aprobación inmutable** | MDG audit trail | Alta | Tabla `approval_decisions` (document_id, approver_id, action, reason, timestamp). No editable. Complementa audit log existente (R-005) |

---

### PRC-3 — Tipos de Orden de Compra

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-08 | **Campo `po_type` en PO: STANDARD / BLANKET / CONTRACT / SCHEDULING** | SAP PO types | Alta | Cada tipo habilita/deshabilita campos relevantes en la UI. Blanket lleva `max_amount` sin líneas de cantidad fija |
| PRC-09 | **Contratos marco con release orders** | SAP Contract + Release | Media | Tabla `procurement_contracts` (vendor_id, value_limit, valid_from, valid_to). POs que referencian el contrato se descuentan del límite automáticamente |
| PRC-10 | **Scheduling agreements con delivery schedule lines** | SAP Scheduling Agreement | Baja | Para proveedores con entregas recurrentes. `scheduling_agreements` + `schedule_lines` (date, qty). MRP genera GRs esperadas |

---

### PRC-4 — Source Determination

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-11 | **Purchasing Info Record (PIR): precio acordado por vendor-producto** | SAP PIR | Alta | Tabla `vendor_product_conditions` (vendor_id, product_id, price, uom, moq, lead_time_days, valid_from, valid_to). Al crear PO: proponer precio desde PIR vigente |
| PRC-12 | **Source List: proveedores aprobados por producto-almacén** | SAP Source List | Media | Tabla `product_approved_vendors` (product_id, warehouse_id, vendor_id, is_preferred, is_blocked, valid_from, valid_to). Si `mandatory=true`: bloquear POs a proveedores fuera de la lista |
| PRC-13 | **Quota arrangement: reparto automático entre proveedores** | SAP Quota Arrangement | Baja | Para split sourcing. `vendor_quotas` (product_id, vendor_id, quota_pct). MRP asigna PRs proporcionalmente |

---

### PRC-5 — RFQ y Evaluación de Proveedores

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-14 | **Módulo de RFQ con comparativa de precios** | SAP ME41/ME49 | Media | Tablas `rfqs` + `rfq_lines` + `vendor_quotations`. Endpoint de comparación: devuelve tabla de precios por proveedor ordenada por precio + criterios adicionales |
| PRC-15 | **Scoring de cotizaciones multi-criterio** | SAP strategic RFQ | Baja | Pesos configurables: precio, lead time, rating histórico. Score = Σ(peso × valor_normalizado). El proveedor con mayor score es el recomendado |
| PRC-16 | **Conversión directa de cotización ganadora en PO** | SAP ME21N desde RFQ | Media | Un clic convierte la quotation seleccionada en PO, precargando todos los datos. Trazabilidad RFQ → PO |

---

### PRC-6 — Invoice Verification

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-17 | **Three-way match automático: PO ↔ GR ↔ Invoice** | SAP MIRO + NetSuite | Alta | Ya identificado en Integración (I-02). Aquí se documenta como mejora de Compras también: al registrar invoice, comparar qty/precio vs PO y GR. Status: matched / tolerance_ok / blocked |
| PRC-18 | **Tolerance keys configurables por tipo de documento y proveedor** | SAP OMR6 | Alta | Tabla `invoice_tolerances` (document_type, vendor_category, tolerance_key, absolute_limit, pct_limit). Si excede: `payment_block = true` automático |
| PRC-19 | **Stochastic block configurable para spot checks** | SAP stochastic block | Baja | Campo `stochastic_block_pct` en configuración AP. Job al registrar invoice: con probabilidad X%, marcar `payment_block = SPOT_CHECK` independiente de tolerancias |
| PRC-20 | **Flujo de liberación de payment block con razón obligatoria** | SAP payment block release | Alta | Para liberar un bloqueo: el usuario debe seleccionar razón (vendor_confirmed / approved_by_manager / price_difference_accepted) + comentario. Todo auditado |

---

### PRC-7 — KPIs y Visibilidad

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRC-21 | **Dashboard de KPIs de procurement** | NetSuite Procurement Dashboard | Media | Endpoints para: PO Cycle Time, Vendor OTD%, Invoice Processing Time, Spend Under Management%, Maverick Spend% |
| PRC-22 | **Spend analysis por categoría, proveedor y período** | SAP spend analysis | Media | Endpoint `/procurement/spend-analysis` con groupBy: vendor / category / month / cost_center. Fuente: POs aprobados + facturas pagadas |
| PRC-23 | **Vendor scorecard automático** | SAP vendor evaluation | Media | Por proveedor: OTD% + calidad (% GRs sin devolución) + precio (vs mercado) + cumplimiento documental. Actualizar mensualmente. Visible en Vendor Master |

---

## Executive Summary — Compras (P2P)

### Los 5 Principios del P2P de la Industria

1. **Sin PO, no hay pago** — El 100% del gasto debe pasar por una PO aprobada. El maverick spend (compras sin PO) es el enemigo del control financiero. Target: <5% de gasto total.

2. **La PR es la primera línea de control** — La aprobación de la PR (antes de comprometer gasto) es más eficiente que revisar la factura al final. Cada nivel de aprobación tiene un límite claro.

3. **El PIR es el contrato operativo** — El precio acordado con el proveedor vive en el Info Record, no en hojas de cálculo. Si el precio del PIR vigente difiere de la factura → alerta automática.

4. **Tolerancias, no excepciones manuales** — El sistema decide automáticamente si una factura pasa o se bloquea. Los humanos solo intervienen en las excepciones reales. Esto escala sin agregar headcount.

5. **KPIs en tiempo real, no reportes mensuales** — PO Cycle Time y Vendor OTD son métricas que el equipo de compras ve diariamente, no al cierre del mes.

---

### Mapa de Mejoras Consolidado — Compras

| ID | Mejora | Prioridad | Complejidad |
|----|--------|-----------|-------------|
| PRC-01 | Purchase Requisition como entidad propia | Alta | Baja |
| PRC-02 | Status lifecycle de PR | Alta | Baja |
| PRC-03 | Auto-conversión PR→PO bajo umbral | Media | Baja |
| PRC-04 | Tabla de aprobación configurable | Alta | Media |
| PRC-05 | Escalación automática por timeout | Alta | Media |
| PRC-06 | Notificaciones al aprobador | Media | Baja |
| PRC-07 | Log de decisiones inmutable | Alta | Baja |
| PRC-08 | Campo po_type en PO | Alta | Baja |
| PRC-09 | Contratos marco + release orders | Media | Media |
| PRC-10 | Scheduling agreements | Baja | Alta |
| PRC-11 | Purchasing Info Record | Alta | Baja |
| PRC-12 | Source List (proveedores aprobados) | Media | Baja |
| PRC-13 | Quota arrangement | Baja | Media |
| PRC-14 | Módulo RFQ con comparativa | Media | Media |
| PRC-15 | Scoring multi-criterio de cotizaciones | Baja | Media |
| PRC-16 | Conversión cotización → PO | Media | Baja |
| PRC-17 | Three-way match automático | Alta | Media |
| PRC-18 | Tolerance keys configurables | Alta | Baja |
| PRC-19 | Stochastic block | Baja | Baja |
| PRC-20 | Flujo liberación payment block | Alta | Baja |
| PRC-21 | Dashboard KPIs procurement | Media | Media |
| PRC-22 | Spend analysis | Media | Media |
| PRC-23 | Vendor scorecard automático | Media | Media |

**Total: 23 mejoras identificadas para el módulo de Compras**

---

### Encadenamiento con Módulos Adyacentes

```
MAESTROS ──────────────────────────────────────────────────
  Vendor Master (M2-*)     → Proveedor en PO, PIR, Source List
  Product Master (M1-*)    → Material en PR, PO, GR
  UoM (M4-*)               → Conversión qty PO ↔ qty GR ↔ qty Invoice
  Pricing Conditions (I-03)→ Precio base del PIR

INVENTARIO ─────────────────────────────────────────────────
  GR (INV-02, INV-05)     → GR cierra el PO; abre GR/IR; actualiza stock
  Lot tracking (INV-06/07)→ Al GR de producto con lote: crear lot record
  Cost lots (INV-12)       → Costo real de GR → AVCO recalculo

SIGUIENTE: PRICING ─────────────────────────────────────────
  PIR price (PRC-11)      → Alimenta condition records de precio de compra
  Contract prices (PRC-09)→ Descuentos negociados → condition technique
```

---

## Technical Research Sources

- [GTR Academy — SAP P2P Process](https://gtracademy.org/procure-to-pay-process-in-sap-mm/)
- [SAP — What is Procure-to-Pay](https://www.sap.com/resources/what-is-procure-to-pay)
- [Stampli — Purchase Requisition Best Practices](https://www.stampli.com/blog/accounts-payable/purchase-requisition-best-practices/)
- [Tipalti — Approval Matrix](https://tipalti.com/resources/learn/approval-matrix/)
- [GEP — PO Approval Process 2026](https://www.gep.com/blog/strategy/purchase-order-approval-process-guide)
- [SAP Learning — Working with Contracts](https://learning.sap.com/courses/purchasing-in-sap-s-4hana/working-with-contracts)
- [CloudBook — Scheduling Agreements](https://cloudbook.co.in/blog/scheduling-agreements-in-sap-mm-a-comprehensive-guide/)
- [TutorialsPoint — SAP Source List](https://www.tutorialspoint.com/sap_mm/sap_mm_source_determination_list.htm)
- [SAP Learning — Source Lists S/4HANA](https://learning.sap.com/learning-journeys/exploring-sourcing-in-s-4hana/introducing-source-lists-sap-s-4hana)
- [Futura Solutions — RFQ Operational vs Strategic](https://www.futura-solutions.de/en/blog/operational-strategic-rfq/)
- [SAP Community — Invoice Tolerance Keys](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/invoice-tolerance-keys-an-insight-part-1/ba-p/13085884)
- [NetSuite — 35 Procurement KPIs](https://www.netsuite.com/portal/resource/articles/erp/procurement-kpis.shtml)
- [Vroozi — 25 Procurement KPIs 2025](https://www.vroozi.com/blog/procurement-kpis-25-essential-metrics-to-track-in-2025/)

---

**Completion Date:** 2026-05-13
**Total mejoras:** 23 · **Fuentes:** 13
**Siguiente módulo:** [Pricing](./technical-erp-pricing-mejores-practicas-research-2026-05-13.md)
