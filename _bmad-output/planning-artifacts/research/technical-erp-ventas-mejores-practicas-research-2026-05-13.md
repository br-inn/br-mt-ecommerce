---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowType: 'research'
research_type: 'technical'
research_topic: 'ERP Ventas / Order-to-Cash (O2C) — mejores prácticas de la industria'
user_name: 'psierra'
date: '2026-05-13'
---

# Research Report: ERP Ventas / Order-to-Cash — Mejores Prácticas

**Flujo:** Maestros ✅ → Inventario ✅ → Compras ✅ → Pricing ✅ → **Ventas** → Billing → Finanzas

---

## El Ciclo O2C — Flujo Completo

```
Necesidad del cliente
      │
      ▼
Quotation (oferta)      ──► Negociación → aceptada → SO / rechazada → cerrada
      │
      ▼
Sales Order (SO)        ──► Pricing engine (PRI-*) + Credit Check + ATP Check
      │                           │ bloqueada por crédito → Credit Manager
      │                           │ bloqueada por stock → Backorder
      ▼
Outbound Delivery       ──► Pick List → Picking → Packing → Quality Check
      │
      ▼
Goods Issue (GI)        ──► Actualiza inventario (↓ stock) + abre AR
      │
      ▼
Billing Document        ──► Genera factura → siguiente módulo
      │
      ▼
Payment / Collection    ──► Dunning si no paga → cierra AR
```

_Fuente: [SAP Community — O2C S/4HANA Guide](https://community.sap.com/t5/technology-blog-posts-by-members/the-ultimate-sap-s-4hana-guide-for-the-order-to-cash-process/ba-p/14223368) · [GTR Academy — Sales Order SAP SD](https://gtracademy.org/how-to-create-a-sales-order-in-sap-sd/)_

---

## Módulo 1 — Tipos de Documentos de Venta

### Jerarquía de documentos SAP SD

| Tipo | Código SAP | Cuándo usar | Genera |
|------|-----------|------------|--------|
| **Inquiry** | IN | Consulta informal del cliente | Nada (es informativo) |
| **Quotation** | QT | Oferta formal con validez y precio fijo | → Sales Order al aceptar |
| **Sales Order** | OR | Pedido confirmado | → Delivery + Billing |
| **Rush Order** | RO | Pedido urgente: entrega y factura en un paso | → Delivery inmediata |
| **Cash Sales** | CS | Venta al contado en mostrador | → Factura inmediata sin crédito |
| **Contract** | WK1/WK2 | Acuerdo marco de ventas por período/valor | → Release Orders |
| **Returns Order** | RE | Devolución del cliente | → Return Delivery + Credit Memo |
| **Credit Memo Request** | CR | Ajuste de precio a favor del cliente | → Credit Memo |
| **Debit Memo Request** | DR | Ajuste de precio a cargo del cliente | → Debit Memo |

**Regla de oro:** todos los documentos de la cadena (Quotation → SO → Delivery → Invoice) quedan encadenados por referencia. Navegar del documento de factura al pedido original es una operación de un clic.

_Fuente: [SAP Learning — Sales Quotation Process](https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-sales-fundamental-business-processes/understanding-sales-quotation-process_c189a9c0-aa19-4643-843b-69f9f56ad5de) · [SAP Press — Order vs Contract Management](https://blog.sap-press.com/what-are-the-differences-between-between-order-and-contract-management-with-sap-s4hana-and-sap-customer-experience)_

---

## Módulo 2 — ATP Check (Available-to-Promise)

### Qué resuelve el ATP

Al crear un SO, el sistema verifica en tiempo real si el material solicitado estará disponible en la fecha deseada. No bloquea el stock — reserva una **promesa de disponibilidad**.

```
ATP Qty = Stock actual
        + Recepciones planeadas (GRs de POs abiertos)
        + Producción planeada
        − Requerimientos confirmados (SOs ya confirmados)
        − Safety Stock reservado
```

Si `ATP Qty ≥ Qty solicitada para la fecha`: confirma la fecha del cliente.
Si `ATP Qty < Qty solicitada`: propone la primera fecha en que habrá suficiente stock.

### Checking Rules — Qué incluir en el cálculo

SAP permite configurar qué elementos participan en el ATP por tipo de documento:

| Elemento | ¿Incluir en ventas? | Notas |
|----------|--------------------|----|
| Stock físico actual | ✅ Siempre | |
| Safety stock | ❌ No consumir | Reservado para emergencias |
| GRs de POs abiertos | ✅ Sí | Con fecha de GR esperada |
| Produción planeada | ✅ Sí si hay manufactura | |
| Stock en QA / bloqueado | ❌ No | No disponible para venta |
| Stock en tránsito | Opcional | Depende del lead time de traslado |

**S/4HANA Advanced ATP (aATP):** cuando llega nuevo stock, el sistema re-evalúa backorders automáticamente y puede mejorar fechas de entrega para clientes de mayor prioridad.

_Fuente: [SAP Community — O2C S/4HANA](https://community.sap.com/t5/technology-blog-posts-by-members/the-ultimate-sap-s-4hana-guide-for-the-order-to-cash-process/ba-p/14223368)_

---

## Módulo 3 — Credit Management en Ventas

### Flujo de bloqueo y liberación

```
SO creado
    │
    ▼
Credit Check (automático)
    │
    ├── PASA ──────────────────────────────────► SO activo → continúa
    │
    └── FALLA (una o más reglas)
            │
            ▼
        SO bloqueado (status: credit hold)
            │
            ▼
        Credit Manager recibe notificación
            │
            ├── Libera manualmente (con razón) ──► SO activo
            ├── Rechaza el pedido ──────────────► SO cancelado
            └── Solicita pago anticipado ───────► SO en espera
```

### Reglas de bloqueo configurables (SAP FSCM)

| Regla | Cuándo bloquea |
|-------|---------------|
| **Límite de crédito excedido** | Deuda abierta + nuevo SO > credit limit |
| **Deuda vencida** | Facturas overdue > X días |
| **Máximo días vencidos** | Factura más antigua > N días |
| **Categoría de riesgo** | Cliente clasificado como alto riesgo |
| **Límite de crédito expirado** | Fecha de vigencia del límite pasó |

**Auto-release:** el sistema puede liberar automáticamente el bloqueo si el cliente realiza un pago que baje su deuda bajo el umbral. Se crea un **Documented Credit Decision (DCD)** por cada acción.

_Fuente: [SAP Press Blog — Credit Management SAP SD](https://blog.sap-press.com/credit-management-operations-in-sap-sd-sap-erp) · [Dynamics 365 — Credit Holds](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-receivable/cm-sales-order-credit-holds)_

---

## Módulo 4 — Outbound Delivery: Pick, Pack, Ship

### El Flujo Estándar

```
Sales Order confirmado
      │
      ▼
Outbound Delivery creada ──► Fecha de picking, warehouse asignado
      │
      ▼
Pick List generada       ──► Agrupación de líneas por ubicación (wave/batch picking)
      │
      ▼
Picking completado       ──► RF scan confirma qty y lote tomado de cada bin
      │
      ▼
Packing                  ──► Asignación a bultos/cajas, peso registrado
      │
      ▼
Quality Check (opcional) ──► Verificación doble de lo que va en el paquete
      │
      ▼
Goods Issue (GI)         ──► Reduce stock · abre AR · dispara billing
      │
      ▼
Shipping confirmation    ──► Tracking # · ASN al cliente · GI fecha = fecha envío
```

### Métodos de picking y cuándo usar cada uno

| Método | Cómo funciona | Mejor para |
|--------|--------------|-----------|
| **Discrete picking** | Una orden a la vez, un picker completo | Órdenes grandes o con requisitos especiales |
| **Batch picking** | Un picker toma ítems de múltiples órdenes en un recorrido | Muchas órdenes pequeñas con SKUs compartidos |
| **Zone picking** | Cada picker cubre una zona; las líneas se consolidan | Almacenes grandes con zonas especializadas |
| **Wave picking** | Se agrupan órdenes en "waves" para optimizar recursos | Operaciones con ventanas de despacho programadas |

_Fuente: [NetSuite — 55 Warehouse Picking Tips](https://www.netsuite.com/portal/resource/articles/ecommerce/warehouse-order-picking-tips.shtml) · [Cyzerg — Pick and Pack Optimization](https://cyzerg.com/blog/optimizing-the-pick-and-pack-process-challenges-and-solutions/)_

---

## Módulo 5 — Returns Management (RMA)

### Flujo de Devolución de Cliente

```
Cliente solicita devolución
      │
      ▼
Returns Order (RE)       ──► RMA # generado · motivo registrado · referencia SO original
      │
      ▼
Return Delivery          ──► Mercadería física llega al almacén
      │
      ▼
Goods Receipt (retorno)  ──► Stock entra en estado "Quality Inspection"
      │
      ▼
Inspección / Decisión
      ├── Restock (unrestricted) ──► Stock disponible nuevamente
      ├── Scrap (baja) ──────────► Movimiento de baja + contabilización
      └── Reparación ────────────► Envío a servicio técnico
      │
      ▼
Credit Memo              ──► Crédito al cliente por el valor devuelto
```

**SAP Advanced Returns Management (ARM):** solución S/4HANA que gestiona el ciclo completo — incluyendo el seguimiento logístico de la mercadería devuelta y las múltiples opciones de resolución (crédito, reenvío, reparación).

_Fuente: [PIKON — SAP ARM](https://www.pikon.com/en/blog/how-sap-advanced-returns-management-optimizes-your-return-process) · [APPSeCONNECT — Sales Return & Credit Memo SAP](https://www.appseconnect.com/how-to-process-a-sales-return-credit-memo-in-sap-erp/)_

---

## Módulo 6 — KPIs de Ventas y Fulfillment

| KPI | Fórmula | Target best-in-class | Frecuencia |
|-----|---------|---------------------|-----------|
| **Perfect Order Rate** | Órdenes on-time + completas + sin daños + bien facturadas / Total | ≥ 97% | Diario |
| **Order Fulfillment Cycle Time** | Fecha GI − Fecha creación SO | < 12 horas (operaciones eficientes) | Diario |
| **Fill Rate** | Líneas despachadas completas / Total líneas pedidas | > 95% | Diario |
| **Backorder Rate** | Órdenes en backorder / Total SOs | < 2% | Diario |
| **Return Rate** | Líneas devueltas / Líneas vendidas | < 3% | Mensual |
| **Quote-to-Order Rate** | Quotations convertidas en SO / Total quotations | > 30% (B2B) | Mensual |
| **Order Accuracy** | SOs despachados sin error / Total SOs | > 99% | Diario |

_Fuente: [NetSuite — Order Fulfillment KPIs](https://www.netsuite.com/portal/resource/articles/erp/order-fulfillment-kpis-metrics.shtml) · [Omniful — Perfect Order Rate](https://www.omniful.ai/blog/top-supply-chain-metrics-fill-rate-lead-time-perfect-order-rate) · [User Solutions — Perfect Order KPI](https://usersolutions.com/blog/perfect-order-fulfillment-kpi)_

---

## Mejoras Aplicables al Sistema — Ventas (O2C)

> Encadena con: Pricing (engine en SO) → Inventario (ATP + GI) → Credit (bloqueo) → Billing (factura del SO).

---

### VEN-1 — Documentos de Venta

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-01 | **Campo `order_type` en SO: STANDARD / RUSH / CASH / CONTRACT_RELEASE / RETURN** | SAP SD order types | Alta | Cada tipo controla el flujo: RUSH omite aprobación de crédito si monto < umbral; CASH genera invoice inmediatamente; RETURN activa flujo RMA |
| VEN-02 | **Quotation como entidad propia con conversión a SO** | SAP Quotation (QT) | Media | Tabla `quotations` con validez (valid_until). Al aceptar: conversión 1-click a SO copiando todas las líneas y precios. Trazabilidad Quotation → SO |
| VEN-03 | **Referencia encadenada en todos los documentos** | SAP document chain | Alta | SO referencia Quotation (si existe). Delivery referencia SO. Invoice referencia Delivery. Navegar la cadena completa desde cualquier documento |
| VEN-04 | **Credit Memo Request y Debit Memo Request como tipos de SO** | SAP CR/DR | Media | Para ajustes de precio post-factura. Genera documento de billing diferente (credit/debit memo) referenciando la factura original |

---

### VEN-2 — ATP Check

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-05 | **ATP check en creación de SO: confirmar fecha de entrega o proponer alternativa** | SAP ATP | Alta | Al confirmar línea de SO: calcular ATP qty para el producto+almacén en la fecha solicitada. Si ATP < qty: proponer primera fecha disponible o alertar |
| VEN-06 | **Checking rules configurables: qué stock incluir en el ATP** | SAP checking rules | Alta | Config por producto/almacén: incluir/excluir safety stock, stock QA, GRs planeados, producción planeada. Sin hardcode |
| VEN-07 | **Re-evaluación de backorders al recibir nuevo stock** | SAP aATP | Media | Job Celery al procesar un GR: buscar SOs en backorder para ese producto y recalcular fechas. Notificar al equipo de ventas si se puede adelantar una entrega |
| VEN-08 | **Reserva de stock al confirmar SO (soft reservation)** | SAP SO reservation | Alta | Al confirmar qty en SO: crear `stock_reservations` (so_line_id, product_id, warehouse_id, qty, expiry). Reduce el ATP disponible para nuevas órdenes |

---

### VEN-3 — Credit Management

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-09 | **Credit check automático al crear/modificar SO** | SAP Credit Management | Alta | Ya identificado en M3-03. Aquí: integrar con el flujo del SO. Si falla: SO queda en status `credit_hold`. Notificación al credit manager |
| VEN-10 | **Auto-release de credit hold al recibir pago del cliente** | SAP FSCM auto-release | Media | Job Celery al registrar pago: re-evaluar crédito del cliente. Si deuda open < límite: liberar automáticamente los SOs en credit_hold. Crear DCD (Documented Credit Decision) |
| VEN-11 | **Exclusion rules para órdenes pequeñas** | SAP credit exclusion | Media | Config: órdenes < $X no pasan credit check. Omite el bloqueo para compras menores que no justifican revisión manual |

---

### VEN-4 — Delivery y Fulfillment

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-12 | **Outbound Delivery como entidad separada del SO** | SAP Delivery (LT) | Alta | Tabla `outbound_deliveries` referenciando el SO. Status: `pending_pick` → `picking` → `packed` → `goods_issued`. Una delivery puede cubrir múltiples SOs (batch); un SO puede tener múltiples deliveries (partials) |
| VEN-13 | **Pick list agrupada (batch/wave picking)** | SAP Transfer Orders + NetSuite | Media | Endpoint que agrupa lines de delivery por bin location (ordenadas para optimizar recorrido). Output: pick list ordenada geográficamente |
| VEN-14 | **Confirmación de picking con lote (scan)** | SAP RF picking | Media | Al confirmar picking: registrar `lot_id` picked y `bin_id` de origen. Si producto es FEFO: validar que el lote tomado es el correcto (el de expiración más próxima) |
| VEN-15 | **Partial delivery configurable por SO** | SAP partial delivery indicator | Media | Por SO o por cliente: permitir/prohibir entregas parciales. Si `partial_delivery = NO`: no despachar hasta tener todo el SO disponible |
| VEN-16 | **Goods Issue dispara actualización de inventario y apertura de AR** | SAP GI posting | Alta | El GI es el evento que actualiza el stock (INV-02), crea el accounting document (deuda del cliente en AR) y habilita la creación de billing |

---

### VEN-5 — Returns (RMA)

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-17 | **Returns Order con RMA# y referencia al SO original** | SAP RE + ARM | Alta | Tabla `return_orders` (rma_number, original_so_id, reason_code, items[]). RMA# generado automáticamente. Motivo obligatorio (damaged / wrong_item / quality / other) |
| VEN-18 | **Return Delivery + inspección + decisión de destino** | SAP ARM decision | Alta | Al recibir la mercadería: inspeccionarla y registrar decisión: `restock` / `scrap` / `repair`. Cada decisión dispara el movimiento de inventario correspondiente |
| VEN-19 | **Credit Memo automático al aprobar devolución** | SAP Credit Memo | Alta | Al marcar devolución como aprobada: crear Credit Memo referenciando el Returns Order + la factura original. El cliente ve el crédito en su cuenta |

---

### VEN-6 — KPIs

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| VEN-20 | **Dashboard O2C: Perfect Order Rate, Fill Rate, Cycle Time** | NetSuite O2C KPIs | Media | Endpoints para los 7 KPIs de ventas. Filtrable por cliente, producto, almacén, período |
| VEN-21 | **Backorder report en tiempo real** | SAP MD04 style | Media | Vista de todos los SOs con líneas en ATP_FAIL o partial. Muestra fecha prometida vs fecha nueva estimada. Herramienta diaria del equipo de ventas |

---

## Executive Summary — Ventas (O2C)

### Los 5 Principios del O2C de la Industria

1. **La Quotation es el contrato verbal** — Permite negociar condiciones sin comprometer stock. Al aceptar, se convierte en SO con un clic, copiando precios y condiciones exactas. Evita renegociaciones post-pedido.

2. **ATP check ≠ reserva de stock** — Confirmar una fecha en el SO no bloquea el inventario; crea una promesa. La reserva real ocurre al crear la Delivery. El ATP debe recalcularse si el SO se demora.

3. **El crédito se gestiona antes de procesar, no después** — Un SO que excede el límite de crédito se bloquea inmediatamente. El credit manager decide con información, no a posteriori sobre una entrega ya hecha.

4. **Perfect Order Rate es el KPI supremo** — On-time + completo + sin daños + correctamente facturado. Las 4 condiciones simultáneas. Una empresa que factura mal pero entrega bien tiene POR bajo. Medir esto obliga a integrar ventas, warehouse y billing.

5. **Las devoluciones son parte del proceso, no una excepción** — El flujo RMA debe estar tan bien diseñado como el flujo de venta. Una devolución mal gestionada destruye la relación con el cliente más que el problema original.

---

### Mapa de Mejoras Consolidado — Ventas

| ID | Mejora | Prioridad | Complejidad |
|----|--------|-----------|-------------|
| VEN-01 | order_type en SO | Alta | Baja |
| VEN-02 | Quotation con conversión a SO | Media | Media |
| VEN-03 | Referencia encadenada documentos | Alta | Baja |
| VEN-04 | Credit/Debit Memo Request | Media | Baja |
| VEN-05 | ATP check en creación SO | Alta | Alta |
| VEN-06 | Checking rules configurables | Alta | Media |
| VEN-07 | Re-evaluación backorders | Media | Media |
| VEN-08 | Soft reservation al confirmar SO | Alta | Media |
| VEN-09 | Credit check automático en SO | Alta | Media |
| VEN-10 | Auto-release credit hold | Media | Media |
| VEN-11 | Exclusion rules crédito | Media | Baja |
| VEN-12 | Outbound Delivery entidad separada | Alta | Media |
| VEN-13 | Pick list agrupada batch/wave | Media | Media |
| VEN-14 | Confirmación picking con lote | Media | Baja |
| VEN-15 | Partial delivery configurable | Media | Baja |
| VEN-16 | Goods Issue → inventario + AR | Alta | Media |
| VEN-17 | Returns Order con RMA# | Alta | Media |
| VEN-18 | Return Delivery + decisión destino | Alta | Media |
| VEN-19 | Credit Memo automático | Alta | Baja |
| VEN-20 | Dashboard O2C KPIs | Media | Media |
| VEN-21 | Backorder report tiempo real | Media | Baja |

**Total: 21 mejoras identificadas para Ventas (O2C)**

---

## Sources

- [SAP Community — O2C S/4HANA Ultimate Guide](https://community.sap.com/t5/technology-blog-posts-by-members/the-ultimate-sap-s-4hana-guide-for-the-order-to-cash-process/ba-p/14223368)
- [GTR Academy — Sales Order SAP SD](https://gtracademy.org/how-to-create-a-sales-order-in-sap-sd/)
- [SAP Learning — Sales Quotation](https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-sales-fundamental-business-processes/understanding-sales-quotation-process_c189a9c0-aa19-4643-843b-69f9f56ad5de)
- [NetSuite — 55 Warehouse Picking Tips](https://www.netsuite.com/portal/resource/articles/ecommerce/warehouse-order-picking-tips.shtml)
- [PIKON — SAP Advanced Returns Management](https://www.pikon.com/en/blog/how-sap-advanced-returns-management-optimizes-your-return-process)
- [SAP Press Blog — Credit Management SD](https://blog.sap-press.com/credit-management-operations-in-sap-sd-sap-erp)
- [Dynamics 365 — Credit Holds](https://learn.microsoft.com/en-us/dynamics365/finance/accounts-receivable/cm-sales-order-credit-holds)
- [NetSuite — Order Fulfillment KPIs](https://www.netsuite.com/portal/resource/articles/erp/order-fulfillment-kpis-metrics.shtml)
- [Omniful — Perfect Order Rate](https://www.omniful.ai/blog/top-supply-chain-metrics-fill-rate-lead-time-perfect-order-rate)

---

**Completion Date:** 2026-05-13 · **Total mejoras:** 21 · **Fuentes:** 9
**Siguiente módulo:** [Billing / Facturación](./technical-erp-billing-mejores-practicas-research-2026-05-13.md)
