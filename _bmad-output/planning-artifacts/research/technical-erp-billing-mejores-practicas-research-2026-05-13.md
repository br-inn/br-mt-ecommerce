---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowType: 'research'
research_type: 'technical'
research_topic: 'ERP Billing / Facturación — mejores prácticas de la industria'
user_name: 'psierra'
date: '2026-05-13'
---

# Research Report: ERP Billing / Facturación — Mejores Prácticas

**Flujo:** Maestros ✅ → Inventario ✅ → Compras ✅ → Pricing ✅ → Ventas ✅ → **Billing** → Finanzas

---

## El Ciclo Invoice-to-Cash

```
Goods Issue / Delivery confirmada
      │
      ▼
Billing Document creado    ──► Pricing copiado del SO (sin recalcular)
      │                        Tax determinado en runtime
      │                        E-invoice generada (CFDI / ZATCA / PDF)
      ▼
Contabilización en FI      ──► Debit: Accounts Receivable (AR)
      │                        Credit: Revenue Account
      │                        Credit: Tax Payable
      ▼
Envío al cliente           ──► Email + portal + EDI según canal
      │
      ▼
Seguimiento y cobranza     ──► Dunning automático por aging bucket
      │
      ├── Pago recibido    ──► Clear AR · Bank reconciliation
      └── No paga          ──► Escalación → legal → bad debt provision
```

---

## Módulo 1 — Tipos de Documento de Billing

| Tipo | Código SAP | Uso | Impacto contable |
|------|-----------|-----|-----------------|
| **Invoice (Factura)** | F2 | Venta estándar post-entrega | Debit AR / Credit Revenue + Tax |
| **Pro Forma Invoice** | F5/F8 | Factura informativa (aduanas, exportación) | **Ninguno** — no contabiliza |
| **Credit Memo** | G2 | Devolución o ajuste a favor del cliente | Debit Revenue / Credit AR |
| **Debit Memo** | L2 | Cargo adicional al cliente (error de precio) | Debit AR / Credit Revenue |
| **Returns Invoice** | RE | Factura de devolución | Reverso del F2 original |
| **Cancellation** | S1 | Anula una factura ya contabilizada | Reverso total del F2 |
| **Invoice List** | LR | Agrupa varias facturas en un documento | Sumario — solo 1 contabilización |
| **Intercompany Invoice** | IV | Entre entidades del mismo grupo | Elimina en consolidación |

**Regla clave:** el billing document **copia** el precio del sales order o delivery — no lo recalcula. Si hay un error de precio en el SO, debe corregirse antes de hacer billing, no después.

_Fuente: [itpathshaala — Billing Document Types SAP SD](https://itpathshaala.com/tutorials/sap-sd/billing-document-types.html) · [SAP S/4HANA Help — Billing Document Type](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/7b24a64d9d0941bda1afa753263d9e39/d96fb6535fe6b74ce10000000a174cb4.html)_

---

## Módulo 2 — Contabilización y Estructura del Asiento

Al contabilizar un billing document en SAP, se generan automáticamente los asientos de FI:

```sql
-- Factura normal (F2):
DR  Accounts Receivable (cliente)     100.00  (precio neto + impuesto)
  CR  Revenue — Product Sales          85.00  (precio neto sin impuesto)
  CR  Tax Payable — VAT 5%              5.00  (5% UAE VAT)
  CR  Revenue — Freight                10.00  (si aplica)

-- Credit Memo (G2) — devolución:
DR  Revenue — Product Sales           85.00
DR  Tax Payable — VAT 5%               5.00
  CR  Accounts Receivable (cliente)   90.00

-- Cancellation (S1) — anulación total:
Exactamente el reverso del F2 original
```

**Cada billing document genera:**
- Un **Billing Document** (SD)
- Un **Accounting Document** (FI) — vinculado permanentemente
- Una **Tax Document** — para declaraciones fiscales

---

## Módulo 3 — Facturación Electrónica (e-Invoicing)

### México — CFDI 4.0

| Aspecto | Detalle |
|---------|---------|
| **Estándar** | CFDI 4.0 (XML con estructura SAT) |
| **Obligatorio** | Prácticamente todos los contribuyentes personas físicas y morales |
| **Flujo** | Empresa genera XML → envía a **PAC** (Proveedor Autorizado de Certificación) → PAC valida y sella con Timbre Fiscal Digital → SAT registra → archivar mínimo 5 años |
| **Complementos obligatorios** | Pago (para cobros diferidos), Carta Porte (transporte), IE (exportaciones) |
| **Novedad 2025-2026** | SAT puede requerir acceso en tiempo real a datos de plataformas digitales (Regla 2.9.2) |
| **Cancelación** | Requiere aceptación del receptor (excepto montos < $1,000 MXN) |

### Saudi Arabia — ZATCA Fatoora (aplica a clientes KSA)

| Aspecto | Detalle |
|---------|---------|
| **Estándar** | XML UBL 2.1 + PDF/A-3 (con QR, UUID, crypto stamp) |
| **Fase 2** | Integración directa del ERP con plataforma Fatoora de ZATCA |
| **B2B** | **Clearance en tiempo real**: la factura debe ser aprobada por ZATCA antes de enviarse al cliente |
| **B2C** | Reporte en modo batch (hasta 24h de diferencia) |
| **Wave 23 (2026)** | Contribuyentes con facturación > SAR 750,000 (años 2022-2024): enero–marzo 2026 |
| **Penalización** | SAR 5,000 – SAR 50,000 por incumplimiento |

_Fuente: [ecosio — CFDI Compliance](https://ecosio.com/en/blog/a-guide-to-cfdi-compliance/) · [VATupdate — CFDI 2025](https://www.vatupdate.com/2025/11/04/briefing-document-electronic-invoicing-and-real-time-reporting-in-mexico-cfdi/) · [Wafeq — ZATCA Phase 2](https://www.wafeq.com/en-sa/e-invoicing-in-saudi-arabia/preparing-for-e-invoicing/zatca-e-invoicing-phase-2) · [EY — ZATCA Wave 23](https://www.ey.com/en_gl/technical/tax-alerts/saudi-arabia-announces-23rd-wave-of-phase-2-e-invoicing-integration)_

---

## Módulo 4 — AR Collections y Dunning

### Flujo de Cobranza

```
Factura emitida
      │ Día 0
      ▼
Recordatorio previo al vencimiento (Día -5)  ──► "Tu factura vence en 5 días"
      │
      ▼ Día 0: fecha de vencimiento
      │
      ├── PAGA ──────────────────────────────────► Clear AR · Cerrado ✓
      │
      └── NO PAGA
              │ Día +5: Dunning Level 1 (cortés)
              │ Día +15: Dunning Level 2 (firme)
              │ Día +30: Dunning Level 3 (formal con intereses)
              │ Día +60: Dunning Level 4 (legal / colección externa)
              │
              └── Provision bad debt si > 90 días
```

### Best Practices 2025

- **Segmentación de clientes**: cuentas de alto riesgo reciben cadencias más agresivas y tempranas. Clientes VIP reciben llamadas personalizadas, no emails automáticos.
- **IA predictiva**: herramientas de 2025 analizan comportamiento histórico para predecir probabilidad de pago tardío y ajustar la cadencia automáticamente.
- **Enviar factura dentro de 24h del GI**: reduce DSO entre 5-8 días promedio.
- **Descuento por pronto pago**: esquema 2/10 Net 30 (2% de descuento si paga en 10 días). Acelerador de cash flow a bajo costo.
- **Resultado medido (SSON 2025)**: centralizar AR + automatizar dunning redujo DSO en 3 días, mejoró resolución de disputas en 59%.

_Fuente: [Gaviti — AR Strategies 2025](https://gaviti.com/top-accounts-receivable-strategies/) · [Growfin — AR Automation 2025](https://www.growfin.ai/blog/accounts-receivable-automation-the-complete-2025-guide-to-efficient-operations) · [HighRadius — Collecting AR Faster](https://www.highradius.com/resources/Blog/collecting-accounts-receivable/)_

---

## Módulo 5 — AR Aging Report y Payment Terms

### Estructura del AR Aging Report

| Bucket | Descripción | Acción típica |
|--------|------------|--------------|
| **Current (no vencido)** | Facturas dentro de plazo | Monitoring |
| **1-30 días vencido** | Pago tardío leve | Recordatorio automático |
| **31-60 días vencido** | Pago tardío moderado | Dunning Level 2 |
| **61-90 días vencido** | Pago tardío grave | Dunning Level 3 + revisar crédito |
| **91-120 días vencido** | Riesgo alto | Dunning Level 4 + suspender crédito |
| **+120 días vencido** | Bad debt probable | Legal / collection agency |

**Payment Terms estándar de la industria:**

| Term Code | Descripción | Cuándo usar |
|-----------|------------|------------|
| **NET30** | Pago a 30 días | Standard B2B |
| **NET60** | Pago a 60 días | Clientes corporativos grandes |
| **2/10 NET30** | 2% descuento si paga en 10 días, vence en 30 | Acelerar cobro |
| **COD** | Pago contra entrega | Clientes nuevos / alto riesgo |
| **PREPAY** | Pago anticipado antes de despacho | Primer pedido / crédito bloqueado |

_Fuente: [Invoiced — AR Aging Guide](https://www.invoiced.com/resources/blog/aging-accounts-receivable) · [Maxio — AR Aging Report](https://www.maxio.com/blog/aging-report)_

---

## Módulo 6 — Revenue Recognition (ASC 606 / IFRS 15)

### El modelo de 5 pasos

| Paso | Qué hacer |
|------|----------|
| 1 | **Identificar el contrato** con el cliente |
| 2 | **Identificar las performance obligations** (qué se prometió: producto, servicio, suscripción) |
| 3 | **Determinar el precio de transacción** (precio neto de descuentos variables) |
| 4 | **Asignar el precio** a cada performance obligation |
| 5 | **Reconocer revenue** cuando/conforme se satisface cada obligation |

**La distinción crítica: Billing ≠ Revenue Recognition**
- **Billing** dispara cuando se entrega el bien/servicio → genera AR
- **Revenue recognition** es una determinación contable de cuándo se cumplió la obligación
- Para una suscripción anual cobrada por adelantado: billing = día 1; revenue = distribuido en 12 meses

**Para br-mt (fases actuales):**
- Venta de producto físico: reconocimiento al momento del GI (transferencia de riesgo)
- Servicios con milestones: reconocimiento por % de avance o por entregable
- Suscripciones futuras: recognición lineal durante el período

_Fuente: [Certinia — ASC 606 / IFRS 15 5 Steps](https://www.certinia.com/resources/industry-101/complying-with-asc-606-and-ifrs-15/) · [BillingPlatform — Revenue Recognition Guide](https://billingplatform.com/revenue-recognition)_

---

## Módulo 7 — KPIs de Billing

| KPI | Fórmula | Target | Frecuencia |
|-----|---------|--------|-----------|
| **DSO (Days Sales Outstanding)** | (AR / Revenue) × días del período | Manufactura: <45 días · SaaS: <35 días | Mensual |
| **CEI (Collection Effectiveness Index)** | (AR_inicio + Facturado − AR_fin) / (AR_inicio + Facturado − AR_corriente) × 100 | > 90% | Mensual |
| **AR Turnover** | Revenue Anual / AR Promedio | > 8x al año | Mensual |
| **Bad Debt Ratio** | Deuda incobrable / Revenue total | < 0.5% | Trimestral |
| **Invoice Accuracy Rate** | Facturas sin corrección / Total facturas | > 99% | Mensual |
| **Time to Invoice** | Horas entre GI y emisión de factura | < 24 horas | Diario |
| **E-Invoice Compliance Rate** | Facturas e-invoice válidas / Total | 100% (obligatorio) | Diario |

_Fuente: [CreditPulse — DSO Benchmarks 2025](https://www.creditpulse.com/blog/days-sales-outstanding-dso-by-industry-2025-benchmarks-data-analysis) · [Kema — AR KPIs 2025](https://www.kema.co/resources/blog/accounts-receivable-kpis-what-to-track-in-2025) · [stuut.ai — DSO Related KPIs](https://www.stuut.ai/blog/dso-related-kpis-metrics)_

---

## Mejoras Aplicables al Sistema — Billing

> Encadena con: Ventas (SO → Billing) → Finanzas (AR + Revenue posting).

---

### BIL-1 — Documentos de Billing

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-01 | **Campo `billing_type` en invoice: STANDARD / PROFORMA / CREDIT_MEMO / DEBIT_MEMO / CANCELLATION** | SAP SD billing types | Alta | Cada tipo controla el flujo contable. PROFORMA no genera asiento. CANCELLATION revierte el documento original |
| BIL-02 | **Billing document referencia siempre al delivery y al SO** | SAP document chain | Alta | `invoices.delivery_id` + `invoices.so_id` obligatorios. Navegar SO → Delivery → Invoice en un query |
| BIL-03 | **Precio copiado del SO, no recalculado** | SAP billing price copy | Alta | Al crear invoice: copiar `unit_price`, `discount`, `tax_amount` desde las líneas del SO. El engine de pricing NO se vuelve a ejecutar |
| BIL-04 | **Credit Memo referencia la invoice original** | SAP G2 reference | Alta | `credit_memos.original_invoice_id` obligatorio. Permite rastrear el crédito emitido a su causa raíz (devolución, ajuste de precio, error) |

---

### BIL-2 — Contabilización

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-05 | **Asiento automático al confirmar invoice: DR AR / CR Revenue / CR Tax** | SAP FI-SD integration | Alta | Al cambiar `invoice.status` a `posted`: crear `journal_entries` automáticamente con las cuentas correctas. Sin intervención manual |
| BIL-06 | **Desglose de revenue por línea de producto** | SAP revenue posting | Alta | Cada línea del invoice genera su propio asiento de revenue en la cuenta correcta (producto físico vs servicio vs flete) |
| BIL-07 | **Vincular billing document con accounting document** | SAP FI link | Alta | `invoices.accounting_document_id` — inmutable una vez contabilizado. Permite reconciliación directa |

---

### BIL-3 — Facturación Electrónica

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-08 | **Generación de CFDI 4.0 para clientes México** | SAT CFDI 4.0 | Alta | Integración con PAC certificado (Finkok, Edicom, SIFEI). Flujo: invoice confirmada → generar XML → enviar a PAC → recibir timbre → guardar UUID + XML sellado |
| BIL-09 | **Integración ZATCA Fatoora para clientes KSA** | ZATCA Phase 2 | Alta | Endpoint de clearance en tiempo real para B2B KSA. La invoice no se envía al cliente hasta recibir aprobación ZATCA. UUID + QR + crypto stamp obligatorios |
| BIL-10 | **Tabla `e_invoice_submissions` para auditoría de cumplimiento** | CFDI + ZATCA audit | Alta | Registrar: invoice_id, authority (SAT/ZATCA), submission_timestamp, response_code, uuid_fiscal, status. Nunca borrar. Retención mínima: 5 años |
| BIL-11 | **Generación de PDF estándar con datos fiscales completos** | Best practice e-invoicing | Alta | Template de PDF: RFC/TRN del emisor y receptor, UUID fiscal (si aplica), desglose de impuestos, condiciones de pago, datos bancarios para transferencia |

---

### BIL-4 — AR Collections y Dunning

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-12 | **Dunning automático por aging buckets** | SAP F150 Dunning | Alta | Job Celery diario: clasificar facturas vencidas en buckets (1-30 / 31-60 / 61-90 / +90). Enviar email automático según nivel. Nivel 4: alerta a equipo legal |
| BIL-13 | **Payment terms configurables con descuento por pronto pago** | SAP payment terms | Alta | Tabla `payment_terms` (code, net_days, discount_pct, discount_days). Al crear invoice: aplicar el payment term del cliente. Calcular descuento si paga en plazo |
| BIL-14 | **AR Aging Report en tiempo real** | ERP AR aging | Media | Endpoint `/finance/ar-aging` con buckets estándar. Filtrable por cliente, vendedor, período. Fuente de verdad para el equipo de cobranza |
| BIL-15 | **Registro de promesas de pago (payment promises)** | Collections best practice | Media | Al contactar a un cliente moroso: registrar `payment_promises` (customer_id, invoice_id, promised_date, promised_amount, agent_id). Alerta si no cumple |
| BIL-16 | **Descuento por pronto pago automático al registrar pago anticipado** | 2/10 Net 30 pattern | Media | Si pago llega dentro del período de descuento: calcular automáticamente el descuento, aplicarlo y generar nota de crédito por la diferencia |

---

### BIL-5 — Revenue Recognition

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-17 | **Separar billing event de revenue recognition event** | ASC 606 / IFRS 15 | Media | `invoices` (billing) vs `revenue_recognition_entries` (cuándo se reconoce). Para ventas simples de producto: coinciden. Para servicios/suscripciones: pueden diferir |
| BIL-18 | **Revenue recognition schedule para servicios con milestones** | ASC 606 Step 5 | Baja | Para SOs de tipo SERVICE: tabla `rev_rec_schedules` (so_id, milestone, planned_date, amount). Al confirmar milestone: reconocer el revenue correspondiente |

---

### BIL-6 — KPIs

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| BIL-19 | **Dashboard de KPIs de billing: DSO, CEI, Time to Invoice** | AR KPI frameworks | Media | Endpoints para los 7 KPIs de billing. DSO calculado en tiempo real desde AR abierto vs revenue del período |
| BIL-20 | **Alerta de facturas no enviadas dentro de 24h del GI** | Best practice: invoice fast | Media | Job Celery: detectar deliveries con GI confirmado hace > 24h sin invoice generada. Notificar al billing team. Reducir DSO |

---

## Executive Summary — Billing

### Los 5 Principios de Billing de la Industria

1. **Billing es un evento, revenue recognition es una decisión contable** — Facturar no siempre equivale a reconocer ingresos. Para servicios, suscripciones o proyectos, el revenue se distribuye en el tiempo conforme se satisfacen las obligations. Conflundir ambos es un error de compliance.

2. **La factura debe emitirse dentro de las 24h del despacho** — Cada día de retraso en enviar la factura es un día de retraso en el cobro. Las organizaciones top reducen DSO 5-8 días solo automatizando este paso.

3. **E-invoicing no es opcional** — CFDI en México y ZATCA en Arabia Saudita son obligaciones legales con sanciones. El ERP debe generar, validar y archivar facturas electrónicas nativas, no como un addon manual.

4. **Dunning automatizado supera al seguimiento manual en 12-18 días de DSO** — La cadencia de cobranza debe ser sistemática, segmentada por riesgo, y ejecutada sin depender de que alguien recuerde enviar un email.

5. **CEI es más accionable que DSO** — El DSO mide el resultado; el CEI mide la efectividad del proceso de cobranza. Organizaciones de alto rendimiento mantienen CEI > 90%.

---

### Mapa de Mejoras Consolidado — Billing

| ID | Mejora | Prioridad | Complejidad |
|----|--------|-----------|-------------|
| BIL-01 | billing_type en invoice | Alta | Baja |
| BIL-02 | Invoice referencia Delivery + SO | Alta | Baja |
| BIL-03 | Precio copiado del SO | Alta | Baja |
| BIL-04 | Credit Memo referencia invoice original | Alta | Baja |
| BIL-05 | Asiento automático al confirmar invoice | Alta | Media |
| BIL-06 | Desglose revenue por línea | Alta | Baja |
| BIL-07 | Invoice ↔ Accounting document linked | Alta | Baja |
| BIL-08 | CFDI 4.0 — México | Alta | Alta |
| BIL-09 | ZATCA Fatoora — KSA | Alta | Alta |
| BIL-10 | Tabla e_invoice_submissions (audit) | Alta | Baja |
| BIL-11 | PDF fiscal estandarizado | Alta | Baja |
| BIL-12 | Dunning automático por aging | Alta | Media |
| BIL-13 | Payment terms configurables | Alta | Baja |
| BIL-14 | AR Aging Report tiempo real | Media | Media |
| BIL-15 | Registro promesas de pago | Media | Baja |
| BIL-16 | Descuento pronto pago automático | Media | Baja |
| BIL-17 | Separar billing de revenue recognition | Media | Media |
| BIL-18 | Rev rec schedule para servicios | Baja | Alta |
| BIL-19 | Dashboard KPIs billing | Media | Media |
| BIL-20 | Alerta factura no emitida en 24h | Media | Baja |

**Total: 20 mejoras identificadas para Billing**

---

## Sources

- [itpathshaala — Billing Document Types SAP SD](https://itpathshaala.com/tutorials/sap-sd/billing-document-types.html)
- [SAP S/4HANA Help — Billing Document Type](https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/7b24a64d9d0941bda1afa753263d9e39/d96fb6535fe6b74ce10000000a174cb4.html)
- [Gaviti — AR Strategies 2025](https://gaviti.com/top-accounts-receivable-strategies/)
- [Growfin — AR Automation 2025](https://www.growfin.ai/blog/accounts-receivable-automation-the-complete-2025-guide-to-efficient-operations)
- [Certinia — ASC 606 / IFRS 15](https://www.certinia.com/resources/industry-101/complying-with-asc-606-and-ifrs-15/)
- [BillingPlatform — Revenue Recognition](https://billingplatform.com/revenue-recognition)
- [ecosio — CFDI Compliance México](https://ecosio.com/en/blog/a-guide-to-cfdi-compliance/)
- [VATupdate — CFDI 2025](https://www.vatupdate.com/2025/11/04/briefing-document-electronic-invoicing-and-real-time-reporting-in-mexico-cfdi/)
- [Wafeq — ZATCA Phase 2](https://www.wafeq.com/en-sa/e-invoicing-in-saudi-arabia/preparing-for-e-invoicing/zatca-e-invoicing-phase-2)
- [EY — ZATCA Wave 23 2026](https://www.ey.com/en_gl/technical/tax-alerts/saudi-arabia-announces-23rd-wave-of-phase-2-e-invoicing-integration)
- [Invoiced — AR Aging Report](https://www.invoiced.com/resources/blog/aging-accounts-receivable)
- [CreditPulse — DSO Benchmarks 2025](https://www.creditpulse.com/blog/days-sales-outstanding-dso-by-industry-2025-benchmarks-data-analysis)
- [Kema — AR KPIs 2025](https://www.kema.co/resources/blog/accounts-receivable-kpis-what-to-track-in-2025)
- [HighRadius — Collecting AR Faster](https://www.highradius.com/resources/Blog/collecting-accounts-receivable/)

---

**Completion Date:** 2026-05-13 · **Total mejoras:** 20 · **Fuentes:** 14
**Siguiente módulo:** Finanzas / Contabilidad (GL, AP, Cost Accounting, Financial Reporting)
