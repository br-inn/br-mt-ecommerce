---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowType: 'research'
research_type: 'technical'
research_topic: 'ERP Finanzas / Contabilidad — mejores prácticas de la industria'
user_name: 'psierra'
date: '2026-05-13'
---

# Research Report: ERP Finanzas / Contabilidad — Mejores Prácticas

**Flujo:** Maestros ✅ → Inventario ✅ → Compras ✅ → Pricing ✅ → Ventas ✅ → Billing ✅ → **Finanzas**

---

## El Ciclo Record-to-Report (R2R)

```
Transacciones Origen (SO / PO / GR / Billing)
      │
      ▼
Asientos Automáticos ──► Universal Journal (FI)  ──► GL Account + Profit Center + Cost Center
      │                   Una sola fuente de verdad     Dimensions en cada línea
      │
      ▼
Controlling (CO) ──► Cost Center Accounting (CCA)
      │               Product Costing (CO-PC)
      │               Profitability Analysis (CO-PA)
      │
      ▼
Period Close ──► Accruals · Depreciation · Revalorización FX · Allocations
      │
      ▼
Financial Statements ──► P&L · Balance Sheet · Cash Flow · Notas
      │
      ▼
Reporting & Analytics ──► KPI Dashboard · Budget vs Actual · Consolidation
```

---

## Módulo 1 — General Ledger (GL)

### 1.1 Universal Journal — La Revolución de SAP S/4HANA

En SAP clásico (ECC), existían múltiples tablas paralelas: BSEG (FI), COEP (CO), GLPCA (PCA), CE1xxxx (CO-PA). En S/4HANA se unificaron en **ACDOCA** (Universal Journal):

| Campo | Descripción | Antes (ECC) |
|-------|-------------|------------|
| `RLDNR` | Ledger ID | Separado por módulo |
| `RBUKRS` | Company Code | Separado |
| `GJAHR/MONAT` | Año/Período | Separado |
| `RACCT` | G/L Account | BSEG separado de COEP |
| `PRCTR` | Profit Center | Solo en PCA |
| `KOSTL` | Cost Center | Solo en CO |
| `MATNR` | Material | Solo en CO-PC |
| `PALEDGER_PCAT` | CO-PA characteristic | Solo en CE tables |

**Principio**: un solo asiento contiene **todas las dimensiones simultáneamente**. Elimina reconciliación FI-CO.

### 1.2 Estructura del Plan de Cuentas (Chart of Accounts)

SAP recomienda una estructura de cuenta de **10 dígitos** con segmentación funcional:

```
Segmento 1: Clase de cuenta (1 dígito)
  1 = Activo    2 = Pasivo    3 = Patrimonio
  4 = Revenue   5 = COGS      6 = OpEx    7 = Otros ingresos/gastos

Segmento 2-3: Subclase (2 dígitos)
  10 = Cash/Bank  11 = AR  12 = Inventory  13 = Fixed Assets
  20 = AP  21 = Accruals  22 = Loans
  40 = Product Revenue  41 = Service Revenue  42 = Other Revenue

Segmento 4-6: Cuenta base (3 dígitos)
  Detalle específico de la cuenta

Segmento 7-8: Reservado para extensiones locales
```

**Principio del plan de cuentas estrecho**: Menos cuentas = cierre más rápido. La granularidad se logra via profit center / cost center / segment, NO multiplicando cuentas GL.

| Rango | Tipo | Ejemplo |
|-------|------|---------|
| 1000-1999 | Current Assets | 1100 Cash, 1200 AR, 1300 Inventory |
| 2000-2999 | Fixed Assets | 2000 PP&E, 2100 Intangibles |
| 3000-3999 | Liabilities | 3000 AP, 3100 Accrued Liabilities |
| 4000-4999 | Equity | 4000 Share Capital, 4100 Retained Earnings |
| 5000-5999 | Revenue | 5000 Product Sales, 5100 Services |
| 6000-6999 | COGS | 6000 Product COGS, 6100 Freight |
| 7000-7999 | Operating Expenses | 7000 Salaries, 7100 Marketing |
| 8000-8999 | Other Income/Expense | 8000 FX Gain/Loss, 8100 Interest |
| 9000-9999 | Statistical / Clearing | 9000 GR/IR, 9100 Intercompany |

### 1.3 Posting Periods — Control de Períodos

```python
# Variante de período fiscal: V3 (Enero-Diciembre)
# Períodos especiales: 13-16 para ajustes de cierre

posting_period_config = {
    "variant": "MT01",
    "fiscal_year_variant": "K4",    # Enero-Diciembre
    "special_periods": 4,           # 4 períodos especiales de ajuste
    "period_controls": {
        # account_type: [from_period, to_period]
        "+": [1, 12],    # Todas las cuentas - período normal
        "A": [1, 16],    # Activos fijos - incluyendo especiales
        "D": [1, 12],    # Deudores (customers)
        "K": [1, 12],    # Acreedores (vendors)
        "M": [1, 12],    # Materiales
        "S": [1, 16],    # GL accounts - incluyendo especiales
    }
}
```

**Regla**: Al cerrar un período, primero bloquear tipo `M` (materiales), luego `D/K` (sub-ledgers), finalmente `S/+` (GL). El orden inverso al cierre permite reversiones controladas.

### 1.4 Ledger Groups — Multi-GAAP

| Ledger | Nombre | Estándar | Uso |
|--------|--------|----------|-----|
| `0L` | Leading Ledger | IFRS | Reporting principal |
| `2L` | Local GAAP | US GAAP / MX PCGA | Reporte local |
| `3L` | Tax | Fiscal local | Declaraciones fiscales |
| `ZL` | Management | Internal | CO-PA / management reporting |

_Fuente: [SAP PRESS — General Ledger Accounting with SAP S/4HANA](https://www.sap-press.com/general-ledger-accounting-with-sap-s4hana_5630/) · [SAP Blog — 11 Features of GL in S/4HANA](https://blog.sap-press.com/11-features-of-general-ledger-accounting-in-sap-s4hana)_

---

## Módulo 2 — Accounts Payable (AP)

### 2.1 Ciclo Procure-to-Pay en FI

```
PO creada (MM)
    │
    ▼
GR recibida ──► DR: Inventory/GR/IR Account   (9000)
               CR: GR/IR Clearing Account     (9000)  ← Cuenta puente abierta

    │
    ▼
Invoice recibida ──► Verificación 3-way match (PRC-17)
                     DR: GR/IR Clearing        (9000)  ← Cierra la cuenta puente
                     CR: Accounts Payable      (3000)  ← Deuda con proveedor
                     [DR/CR: Price Difference  (8000)] ← Si precio difiere del PO

    │
    ▼
APP (F110) ──► DR: Accounts Payable           (3000)  ← Cancela deuda
               CR: Bank / Clearing            (1100)  ← Pago bancario
```

### 2.2 Automatic Payment Program (APP) — F110

El APP de SAP es el motor de pagos masivos. Configuración clave:

```python
# Configuración del APP (Transaction F110)
app_config = {
    "payment_run_id": "MT_2026_05_13",
    "company_codes": ["MT01"],
    "payment_methods": ["T"],          # T = Bank Transfer
    "next_payment_date": "2026-05-20", # Fecha del próximo pago
    "document_types": ["KR", "RE"],    # Facturas de proveedor

    # Criterios de selección
    "selection": {
        "vendors": "*",                # Todos los proveedores
        "due_date_from": "2026-01-01",
        "due_date_to": "2026-05-20",   # Pagar todo lo que vence hasta HOY+7
        "minimum_amount": 50.00,       # No pagar importes menores a 50
    },

    # Regla de pago anticipado (early payment discount)
    "discount_rules": {
        "2/10 NET30": {
            "discount_pct": 2.0,
            "discount_days": 10,
            "net_days": 30
        }
    }
}

# Los 4 pasos del APP (las 4 P)
app_steps = [
    "1. Parameters    — Definir rango, métodos, fechas",
    "2. Proposal      — Simular qué se va a pagar (revisable)",
    "3. Payment       — Ejecutar el pago (genera documentos FI)",
    "4. Print/Output  — Generar archivo bancario (SEPA XML / BACS / ACH)",
]
```

**Control crítico**: Nunca saltar el paso Proposal. El equipo de AP debe revisar y aprobar antes de ejecutar Payment. El Proposal puede ser editado: excluir facturas, cambiar importes, cambiar banco.

### 2.3 Aging de Proveedores (AP Aging)

```sql
-- Estructura de aging report de proveedores
SELECT
    v.vendor_id,
    v.vendor_name,
    SUM(CASE WHEN oi.days_overdue <= 0          THEN oi.open_amount ELSE 0 END) AS current_amount,
    SUM(CASE WHEN oi.days_overdue BETWEEN 1  AND 30 THEN oi.open_amount ELSE 0 END) AS bucket_1_30,
    SUM(CASE WHEN oi.days_overdue BETWEEN 31 AND 60 THEN oi.open_amount ELSE 0 END) AS bucket_31_60,
    SUM(CASE WHEN oi.days_overdue BETWEEN 61 AND 90 THEN oi.open_amount ELSE 0 END) AS bucket_61_90,
    SUM(CASE WHEN oi.days_overdue > 90              THEN oi.open_amount ELSE 0 END) AS bucket_90plus,
    SUM(oi.open_amount) AS total_outstanding
FROM vendor_open_items oi
JOIN vendors v ON v.vendor_id = oi.vendor_id
WHERE oi.cleared_date IS NULL
GROUP BY v.vendor_id, v.vendor_name
ORDER BY total_outstanding DESC;
```

**DPO (Days Payable Outstanding)**: `(AP / COGS) × días_período`. Target: 45-60 días (maximizar float sin dañar relación con proveedor).

### 2.4 Reconciliación Bancaria Automática

```python
# Proceso de reconciliación bancaria
bank_recon_flow = {
    "step_1": "Upload bank statement file (BAI2/MT940/CAMT.053)",
    "step_2": "Auto-match: payment amount + date + reference",
    "step_3": "Post matched items: clear AP open item against bank",
    "step_4": "Review exceptions: unmatched items",
    "step_5": "Manual posting for exceptions",
    "step_6": "Balance = Bank Statement Balance == GL Bank Account Balance",
}

# Tabla de reglas de matching automático
matching_rules = [
    {"rule": "exact_match",    "criteria": ["amount", "reference"],     "auto_post": True,  "confidence": 100},
    {"rule": "amount_match",   "criteria": ["amount", "date ±2 days"],  "auto_post": True,  "confidence": 95},
    {"rule": "fuzzy_match",    "criteria": ["amount ±0.01", "vendor"],  "auto_post": False, "confidence": 80},
    {"rule": "no_match",       "criteria": [],                          "auto_post": False, "confidence": 0},
]
```

_Fuente: [SAP Automatic Payment Program Guide](https://www.sap-press.com/automatic-payment-program-in-sap-accounts-payable-running-and-troubleshooting_4189/) · [SAP Community — APP Configuration](https://community.sap.com/t5/financial-management-blog-posts-by-members/understanding-automatic-payment-program-configuration/ba-p/14144597)_

---

## Módulo 3 — Controlling (CO): Cost Centers y Profit Centers

### 3.1 Jerarquía de Centros de Costo

```
Empresa (Company Code: MT01)
└── División (Division: Middle East Operations)
    ├── Área Funcional 1: Ventas & Marketing
    │   ├── CC: 1010 — Ventas ME
    │   ├── CC: 1020 — Marketing Digital
    │   └── CC: 1030 — Atención al Cliente
    ├── Área Funcional 2: Operaciones
    │   ├── CC: 2010 — Almacén / Warehouse
    │   ├── CC: 2020 — Logística
    │   └── CC: 2030 — Control de Calidad
    ├── Área Funcional 3: Tecnología
    │   ├── CC: 3010 — Infraestructura IT
    │   └── CC: 3020 — Desarrollo de Software
    └── Área Funcional 4: G&A (General & Administrative)
        ├── CC: 4010 — Finanzas & Contabilidad
        ├── CC: 4020 — RRHH
        └── CC: 4030 — Dirección General
```

**Regla de diseño**: El cost center captura COSTOS. El profit center captura INGRESOS + COSTOS para ver P&L por segmento. No son lo mismo.

### 3.2 Profit Centers — Reporte P&L por Segmento

| Profit Center | Negocio | Revenue | Costs | Margin |
|--------------|---------|---------|-------|--------|
| `PC_BSMT`   | B2C e-commerce (MENA) | ✅ | ✅ | ✅ |
| `PC_BSMT_AE` | UAE específico | ✅ | ✅ | ✅ |
| `PC_BSMT_SA` | KSA específico | ✅ | ✅ | ✅ |
| `PC_INTERN`  | Internal / projects | ❌ | ✅ | ❌ |

**SAP PCA (Profit Center Accounting)**: Cada asiento FI genera automáticamente una línea paralela en el ledger del profit center. No requiere posteo manual.

### 3.3 Activity-Based Costing — Precio de Actividad

```python
# Plan de actividades por cost center
activity_price_calculation = {
    "cost_center": "2010_Almacen",
    "activity_type": "PICK",           # Unidad de actividad: 1 línea de picking
    "planned_costs": 120_000,          # USD/año total del CC
    "planned_activity_qty": 50_000,    # líneas de picking/año
    "plan_activity_price": 2.40,       # USD por línea de picking

    # Al confirmar un delivery (picking), se imputa:
    # DR: Product Cost (CO-PC order)  — $2.40 × líneas
    # CR: Cost Center Almacén         — absorbe el costo
}
```

_Fuente: [SAP CO Best Practices — Surety Systems](https://www.suretysystems.com/insights/improving-profitability-and-cost-control-with-sap-co-functionality/) · [ERP Corp — Product Cost Controlling S/4HANA](https://controlling.erpcorp.com/sap-controlling-blog/sap-product-cost-controlling-s4hana)_

---

## Módulo 4 — Product Costing (CO-PC)

### 4.1 Tipos de Costo de Producto

| Tipo | Descripción | Cuándo se usa |
|------|-------------|---------------|
| **Standard Cost** | Costo teórico calculado al inicio del período | Manufacturing: valuation base para varianzas |
| **Actual Cost** | Costo real acumulado en la orden | Al cerrar la orden: varianzas vs standard |
| **Moving Average** | AVCO: recalcula con cada entrada | Trading / distribución |
| **FIFO / FEFO** | Consume lotes más antiguos primero | Perecederos, commodities |

### 4.2 Standard Cost Roll (Estimación de Costos)

```
Materiales comprados (Material Master)
        │ precio de compra (PIR — PRC-11)
        ▼
Bill of Materials (BOM)
        │ estructura del producto
        ▼
Routing / Work Centers
        │ horas máquina + mano de obra
        ▼
Overhead (Costing Sheet)
        │ % sobre material o mano de obra
        ▼
Standard Cost (Estimación de Costo)
        │ costo total por unidad
        ▼
Mark + Release ──► Válido para el período fiscal
```

**En trading/distribución** (sin manufactura), el costo estándar se basa en: precio de PO + flete estimado + duties + handling cost.

### 4.3 Varianzas de Costo

```python
# Al recibir mercancía (GR):
# Si precio PO != precio standard del material:

variance_posting = {
    "type": "Price Difference",
    "trigger": "GR when PO_price != standard_price",
    "entry": {
        "DR": ("Inventory at Standard", standard_price * qty),
        "DR/CR": ("Price Difference Account 8000", abs(po_price - standard_price) * qty),
        "CR": ("GR/IR Clearing 9000", po_price * qty),
    }
}

# Varianzas de producción (si aplica):
production_variances = {
    "usage_variance":  "BOM qty consumed != BOM qty planned",
    "price_variance":  "Actual material price != standard",
    "activity_variance": "Actual hours != planned hours",
    "overhead_variance": "Actual overhead != absorbed overhead",
}
```

### 4.4 CO-PA — Profitability Analysis

CO-PA responde: **¿Cuánto ganamos POR CLIENTE, POR PRODUCTO, POR CANAL?**

```python
# Características (dimensions) de CO-PA
copa_characteristics = [
    "customer_id",        # Cliente
    "product_id",         # Producto / SKU
    "product_group",      # Familia de producto
    "sales_channel",      # Canal: B2C / B2B / Marketplace
    "country",            # País del cliente
    "region",             # Región ME
    "profit_center",      # Profit center asignado
    "period",             # Mes/año
]

# Value fields (métricas) de CO-PA
copa_value_fields = {
    "VKE001": "Gross Revenue (antes de descuentos)",
    "VKE002": "Sales Deductions (descuentos cliente)",
    "VKE003": "Net Revenue",
    "VKE004": "COGS — Material",
    "VKE005": "COGS — Freight",
    "VKE006": "Gross Profit",
    "VKE007": "Allocated Selling Costs",
    "VKE008": "Contribution Margin",
}
```

_Fuente: [SAP PRESS — Product Cost Controlling S/4HANA](https://www.sap-press.com/product-cost-controlling-with-sap-s4hana_5832/) · [Surety Systems — SAP CO Functionality](https://www.suretysystems.com/insights/improving-profitability-and-cost-control-with-sap-co-functionality/)_

---

## Módulo 5 — Financial Reporting & Period Close

### 5.1 Fast Close — El Objetivo: 3-Day Close

HighRadius y KPMG documentan que el estándar de la industria 2025 es el **3-Day Close** (cierre en 3 días hábiles vs el histórico de 10 días). Las claves:

```
Día T-5 (5 días antes del cierre oficial):
  ✅ Reconciliar cuentas de alto volumen durante el mes (no al final)
  ✅ Pre-accruals configurados (Celery Beat para accruals periódicos)

Día T-3:
  ✅ Corte de inventario confirmado (INV-24 — cycle count)
  ✅ GR/IR clearing review: abrir ítems > 30 días → investigar

Día T-2:
  ✅ Reconciliar intercompany
  ✅ Depreciation run automática
  ✅ FX Revaluation (activos y pasivos en moneda extranjera)
  ✅ Accruals manuales (facturas pendientes de recibir)

Día T-1 (último día hábil del mes):
  ✅ Cierre de período MM (bloquear posteos a materiales)
  ✅ Allocations CO (distribuir costos de CC a profit centers)
  ✅ Profit center settlement

Día T (primer día del nuevo mes):
  ✅ Cierre de período FI
  ✅ Generar financial statements
  ✅ Variance analysis: Budget vs Actual
  ✅ Management report distribuido
```

### 5.2 Checklist de Cierre — Estructura Automatizable

```python
# period_close_checklist.py
period_close_tasks = [
    # MM Close
    {"order": 1,  "module": "MM",  "task": "inventory_cutoff",        "auto": True,  "deadline": "T-1 09:00"},
    {"order": 2,  "module": "MM",  "task": "gr_ir_clearing_review",   "auto": False, "deadline": "T-2 EOD"},
    {"order": 3,  "module": "MM",  "task": "close_mm_period",         "auto": True,  "deadline": "T-1 17:00"},

    # FI Close
    {"order": 4,  "module": "FI",  "task": "depreciation_run",        "auto": True,  "deadline": "T-1 18:00"},
    {"order": 5,  "module": "FI",  "task": "fx_revaluation",          "auto": True,  "deadline": "T-1 19:00"},
    {"order": 6,  "module": "FI",  "task": "accruals_posting",        "auto": False, "deadline": "T-1 20:00"},
    {"order": 7,  "module": "FI",  "task": "bank_reconciliation",     "auto": True,  "deadline": "T 09:00"},
    {"order": 8,  "module": "FI",  "task": "intercompany_recon",      "auto": False, "deadline": "T 10:00"},

    # CO Close
    {"order": 9,  "module": "CO",  "task": "overhead_allocations",    "auto": True,  "deadline": "T 11:00"},
    {"order": 10, "module": "CO",  "task": "production_settlement",   "auto": True,  "deadline": "T 12:00"},
    {"order": 11, "module": "CO",  "task": "copa_transfer",           "auto": True,  "deadline": "T 13:00"},

    # Reporting
    {"order": 12, "module": "REP", "task": "generate_financials",     "auto": True,  "deadline": "T 14:00"},
    {"order": 13, "module": "REP", "task": "budget_vs_actual",        "auto": True,  "deadline": "T 15:00"},
    {"order": 14, "module": "REP", "task": "management_pack",         "auto": False, "deadline": "T 17:00"},
]
```

### 5.3 Estados Financieros — Los 3 Obligatorios

**Income Statement (P&L):**
```
Revenue                          1,000,000
  (-) Sales Deductions              (50,000)
Net Revenue                        950,000
  (-) COGS                        (600,000)
Gross Profit                       350,000   [GP% = 36.8%]
  (-) Operating Expenses           (200,000)
    Selling & Distribution          (80,000)
    G&A                             (70,000)
    Technology                      (50,000)
EBITDA                             150,000   [EBITDA% = 15.8%]
  (-) Depreciation & Amortization   (20,000)
EBIT                               130,000
  (-) Interest Expense              (10,000)
EBT                                120,000
  (-) Income Tax (9% UAE CIT)       (10,800)
Net Income                         109,200   [Net Margin = 11.5%]
```

**Balance Sheet Structure:**
```
ASSETS                              LIABILITIES & EQUITY
Current Assets:                     Current Liabilities:
  Cash & Bank          100,000        Accounts Payable      150,000
  Accounts Receivable  200,000        Accrued Liabilities    30,000
  Inventory            300,000        VAT Payable            20,000
  Prepaid Expenses      20,000        Short-term Debt        50,000
Non-Current Assets:                 Non-Current Liabilities:
  Fixed Assets (net)   500,000        Long-term Debt        200,000
  Intangibles           80,000      Equity:
                                      Share Capital         450,000
                                      Retained Earnings     300,000
TOTAL ASSETS         1,200,000     TOTAL L+E             1,200,000
```

**Cash Flow (Indirect Method):**
```
Net Income                           109,200
+ Depreciation & Amortization         20,000
+/- Changes in Working Capital:
  - Increase in AR                   (30,000)
  + Increase in AP                    20,000
  + Decrease in Inventory             10,000
Operating Cash Flow                  129,200   [OCF]

Investing Activities:
  - Capital Expenditures             (50,000)
Free Cash Flow                        79,200   [FCF]

Financing Activities:
  - Loan Repayments                  (20,000)
Net Cash Flow                         59,200
```

### 5.4 Budget vs Actual — Variance Analysis

```python
# Estructura de presupuesto en ERP
budget_structure = {
    "budget_version": "2026_APPROVED",
    "granularity": "monthly",          # Presupuesto por mes
    "dimensions": ["profit_center", "cost_center", "gl_account"],
    "tolerance_rules": {
        "revenue_favorable":  {"pct": 5,  "action": "info"},
        "revenue_adverse":    {"pct": 3,  "action": "alert"},
        "opex_adverse":       {"pct": 10, "action": "alert"},
        "opex_critical":      {"pct": 20, "action": "escalate_to_cfo"},
    }
}

# Report: Budget vs Actual por línea P&L
def budget_variance_report(period: str, profit_center: str):
    return {
        "columns": ["account", "budget", "actual", "variance_abs", "variance_pct", "status"],
        "note": "Negative variance = over budget. Positive variance in revenue = favorable.",
    }
```

_Fuente: [HighRadius — Month-End Close Process 2026](https://www.highradius.com/resources/Blog/what-is-month-end-close-process/) · [Numeric — Financial Close Process](https://www.numeric.io/blog/financial-close-process) · [NetSuite — Financial Reporting Best Practices](https://bigbang360.com/optimizing-financial-reporting-with-netsuite/)_

---

## Módulo 6 — Cash Management & Treasury

### 6.1 Cash Flow Forecasting

```python
# Componentes del cash flow forecast (rolling 13 weeks)
cash_forecast_components = {
    "inflows": {
        "ar_collections": "AR aging × collection probability por bucket",
        "advance_payments": "SO con payment terms PREPAY",
        "other_income": "Manual input",
    },
    "outflows": {
        "ap_payments": "Vendor open items × APP next run date",
        "payroll": "Fixed schedule desde RRHH",
        "tax_payments": "VAT filing dates (UAE = monthly, KSA = quarterly)",
        "capex": "Purchase orders de activos fijos",
        "loan_repayments": "Schedule de deuda",
    },
    "output": {
        "net_position_by_week": "Cash + Inflows - Outflows",
        "min_cash_balance": "Policía mínimo: 3 meses de OpEx",
        "alert_threshold": "Si forecast < min_cash_balance → alert CFO",
    }
}
```

### 6.2 UAE CIT (Corporate Income Tax) — 9% desde 2023

Emiratos introdujo CIT en junio 2023 a tasa del 9% sobre beneficios > AED 375,000:

```python
uae_cit_rules = {
    "tax_rate": 0.09,
    "threshold_aed": 375_000,        # Beneficio exento hasta este monto
    "small_business_relief": True,   # Disponible para revenue < AED 3M
    "free_zone_rate": 0.00,          # Free zones calificadas: 0% CIT
    "filing_deadline": "9 months after fiscal year end",
    "payment_deadline": "9 months after fiscal year end",
    # Provisional instalments: disponibles pero no obligatorios en 2024/2025
}

# Asiento de CIT:
# DR: Income Tax Expense           (9% × EBT)
# CR: Income Tax Payable           (corriente liability)
# → Al pagar: DR Tax Payable / CR Bank
```

### 6.3 Intercompany Reconciliation

Para grupos con múltiples entidades (ej. MT UAE + MT KSA):

```python
intercompany_flow = {
    "intra_group_sale": {
        "seller": "MT_UAE",
        "buyer": "MT_KSA",
        "GL_seller": "DR Intercompany Receivable / CR Intercompany Revenue",
        "GL_buyer": "DR Intercompany Expense / CR Intercompany Payable",
        "elimination_at_consolidation": "Must net to zero",
    },
    "recon_rule": "Ambas entidades deben cuadrar al centavo antes del cierre",
    "tool": "Matching por documento de referencia intercompany (ICN número)",
}
```

_Fuente: [SAP Cash Management Guide](https://www.tutorialspoint.com/sap_fico/sap_fi_cash_management.htm) · [Numeric — Cash Reconciliation 2025](https://www.numeric.io/blog/cash-reconciliation-guide)_

---

## Mejoras Aplicables al Sistema (br-mt-ecommerce)

| # | Mejora | Inspiración | Prioridad | Notas de implementación |
|---|--------|-------------|-----------|------------------------|
| **FIN-01** | **Universal Journal**: tabla `financial_entries` con dimensiones GL+CostCenter+ProfitCenter+Project en una sola fila | SAP ACDOCA / S/4HANA | 🔴 CRÍTICA | Elimina reconciliación entre módulos. Única fuente de verdad para todos los reportes |
| **FIN-02** | **Chart of Accounts standardizado**: rango 1000-8999 con segmentación funcional, máximo 200 cuentas activas | NetSuite / SAP FICO | 🔴 CRÍTICA | Hoy no existe CoA formal. Crear tabla `gl_accounts` con `account_code`, `account_type`, `normal_balance`, `is_active` |
| **FIN-03** | **Posting Periods control**: tabla `posting_periods` por tipo de cuenta (GL/AP/AR/Inventory) con open/close por mes | SAP Variant de Período | 🔴 CRÍTICA | Impedir posteos al período anterior una vez cerrado. Soft-lock primero, hard-lock tras cierre |
| **FIN-04** | **AP Aging Report** automatizado: 5 buckets (current/1-30/31-60/61-90/90+) generado diariamente via Celery | SAP FBL1N / NetSuite | 🟠 ALTA | Input de PRC-17 (facturas de proveedor). Conecta con payment run |
| **FIN-05** | **Automatic Payment Run** configurable: programar pagos por fecha de vencimiento, método de pago, monto mínimo | SAP F110 / Odoo | 🟠 ALTA | Tabla `payment_runs` con estado (draft→proposed→approved→executed). Generar archivo bancario |
| **FIN-06** | **Early Payment Discount Engine**: `2/10 NET30` → capturar ahorro si paga en día 10. Registro en G/L | SAP Cash Discount / NetSuite | 🟡 MEDIA | Al ejecutar pago anticipado: DR AP neto / CR Bank total / CR Cash Discount Income |
| **FIN-07** | **Vendor Statement Reconciliation**: comparar `vendor_open_items` con estado de cuenta externo del proveedor | SAP MRBR / Odoo | 🟡 MEDIA | Workflow de excepciones para diferencias. Flag ítems > 60 días sin conciliar |
| **FIN-08** | **Bank Reconciliation automática**: importar extracto bancario (CSV/MT940), matching automático por importe+referencia | SAP FF67 / NetSuite | 🟠 ALTA | Tabla `bank_statement_lines`. Auto-clear si match 100%. Queue manual para excepciones |
| **FIN-09** | **Cost Center Hierarchy**: árbol de CC por función (Ventas/Ops/Tech/G&A). Toda transacción con gasto requiere CC | SAP CCA / Odoo | 🟠 ALTA | Tabla `cost_centers` con `parent_id` (jerarquía). FK obligatoria en journal entries de gasto |
| **FIN-10** | **Profit Center P&L**: cada venta y cada costo asignado a un profit center → P&L por segmento de negocio | SAP PCA / NetSuite Segments | 🔴 CRÍTICA | Tabla `profit_centers`. Revenue conectado desde BIL-05 (billing document). Base para decisiones estratégicas |
| **FIN-11** | **Standard Cost por SKU**: precio standard calculado = material cost + freight + duties + handling. Actualizable por período | SAP CO-PC / Odoo Standard Price | 🟠 ALTA | Conecta con INV-02 (AVCO/FIFO). Tabla `product_standard_costs` con `valid_from`/`valid_to` |
| **FIN-12** | **Varianza de Precio de Compra**: al recibir GR con precio distinto al standard → posteo automático a cuenta `8000 Price Difference` | SAP PRD Account | 🟠 ALTA | Conecta con PRC-17 (three-way match). Alerta si varianza > 5% del standard |
| **FIN-13** | **CO-PA básico**: tabla de contribución por canal + producto + cliente. Revenue − COGS − Freight = Contribution Margin | SAP CO-PA / NetSuite | 🟡 MEDIA | Vista materializada `copa_summary` actualizada al billing. Base para pricing decisions (PRI-01) |
| **FIN-14** | **Period Close Checklist** automatizada: tabla `period_close_tasks` con orden, módulo, estado, responsable y deadline | SAP FBICF / Numeric | 🟠 ALTA | Celery Beat dispara tareas automáticas en orden. Dashboard de estado de cierre en tiempo real |
| **FIN-15** | **P&L Real-time**: vista materializada `income_statement_view` refrescada on-demand. Drill-down a nivel de transaction | NetSuite / SAP S/4HANA | 🔴 CRÍTICA | Conecta con BIL-05 (revenue posting) y FIN-09 (cost centers). Sin esperar al cierre mensual |
| **FIN-16** | **Balance Sheet Reconciliation**: para cuentas clave (AR, AP, Inventory, Bank) → saldo GL = suma de sub-ledger items | KPMG / Numeric | 🟠 ALTA | Tarea automática Celery: comparar `SUM(open_items)` vs `gl_balance`. Alert si diferencia > 0 |
| **FIN-17** | **Cash Flow Statement** (método indirecto): calculado automáticamente desde Net Income + movimientos de working capital | IFRS/NetSuite | 🟡 MEDIA | Mapa de cuentas → categoría de cash flow (Operating/Investing/Financing). Actualizar al billing |
| **FIN-18** | **13-Week Cash Forecast**: combinar AR aging (por cobrar) + AP aging (por pagar) + payroll schedule → posición neta semanal | SAP CM / HighRadius | 🟡 MEDIA | Dashboard para CFO. Alert si posición < 3 meses de OpEx |
| **FIN-19** | **UAE CIT provisioning**: calcular provision de impuesto (9% × EBT) automáticamente al cierre mensual. Asiento automático | UAE Federal Tax Authority | 🔴 CRÍTICA | Conecta con FIN-15 (P&L). Solo si beneficio > AED 375,000. Diferencia temporal vs permanente |
| **FIN-20** | **FX Revaluation al cierre**: revaluar saldos AR/AP/Bank en moneda extranjera al tipo de cambio de fin de mes | SAP FAGL_FC_VAL / IAS 21 | 🟠 ALTA | Conecta con PRI-18 (FX rates diarios). DR/CR FX Gain-Loss Account (8000). Solo para cierre contable |
| **FIN-21** | **Journal Entry controls (SoD)**: 3 roles separados: Preparer → Reviewer → Approver. Sin auto-aprobación | KPMG Audit Standards / SOX | 🟠 ALTA | Tabla `journal_approvals` con estado workflow. Conecta con sistema de roles de usuarios |
| **FIN-22** | **Budget vs Actual dashboard**: comparar presupuesto aprobado (`budget_lines`) vs actual (`financial_entries`) por CC y GL | NetSuite / Odoo | 🟡 MEDIA | Tabla `budget_versions` + `budget_lines`. Variance alert si > 10% adverso en gastos |

**Total módulo Finanzas: 22 mejoras (FIN-01 → FIN-22)**

---

## Arquitectura Recomendada — Tablas Core

```sql
-- Plan de Cuentas
CREATE TABLE gl_accounts (
    account_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_code     VARCHAR(10) UNIQUE NOT NULL,  -- Ej: '5000'
    account_name     VARCHAR(100) NOT NULL,
    account_type     VARCHAR(20) NOT NULL,          -- ASSET/LIABILITY/EQUITY/REVENUE/EXPENSE
    normal_balance   VARCHAR(6) NOT NULL,           -- DEBIT/CREDIT
    is_reconciling   BOOLEAN DEFAULT FALSE,         -- Cuentas que requieren reconciliación mensual
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Universal Journal (una sola tabla para todas las transacciones)
CREATE TABLE financial_entries (
    entry_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_number     VARCHAR(20) UNIQUE NOT NULL,  -- FE-2026-001234
    journal_date     DATE NOT NULL,
    posting_period   VARCHAR(7) NOT NULL,           -- '2026-05'
    entry_type       VARCHAR(20) NOT NULL,          -- AUTO/MANUAL/REVERSAL
    source_module    VARCHAR(20) NOT NULL,          -- BILLING/PURCHASING/PAYROLL/MANUAL
    source_document  UUID,                          -- FK al documento origen

    -- Dimensiones de imputación
    gl_account_id    UUID REFERENCES gl_accounts(account_id),
    cost_center_id   UUID REFERENCES cost_centers(cc_id),
    profit_center_id UUID REFERENCES profit_centers(pc_id),

    -- Importes (siempre en transactional + functional currency)
    debit_amount     NUMERIC(18,2) DEFAULT 0,
    credit_amount    NUMERIC(18,2) DEFAULT 0,
    currency_code    CHAR(3) NOT NULL,
    amount_local     NUMERIC(18,2),                -- En moneda funcional (AED/USD)
    fx_rate          NUMERIC(10,6),

    -- Audit
    description      TEXT,
    preparer_id      UUID NOT NULL,
    reviewer_id      UUID,
    approver_id      UUID,
    approved_at      TIMESTAMPTZ,
    is_reversed      BOOLEAN DEFAULT FALSE,
    reversal_of      UUID REFERENCES financial_entries(entry_id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT entries_balanced CHECK (
        -- Cada documento debe estar balanceado (suma débitos = suma créditos)
        -- Implementar via trigger a nivel de document_header
        TRUE
    )
);
CREATE INDEX idx_fin_entries_period ON financial_entries(posting_period);
CREATE INDEX idx_fin_entries_account ON financial_entries(gl_account_id);
CREATE INDEX idx_fin_entries_date    ON financial_entries(journal_date);

-- Control de períodos
CREATE TABLE posting_periods (
    period_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fiscal_period    VARCHAR(7) NOT NULL,   -- '2026-05'
    account_type     CHAR(1) NOT NULL,      -- '+' ALL / 'D' AR / 'K' AP / 'M' Materials / 'S' GL
    status           VARCHAR(10) NOT NULL,  -- OPEN/SOFT_CLOSED/CLOSED
    opened_at        TIMESTAMPTZ,
    closed_at        TIMESTAMPTZ,
    closed_by        UUID,
    UNIQUE(fiscal_period, account_type)
);

-- Cost Centers
CREATE TABLE cost_centers (
    cc_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cc_code          VARCHAR(10) UNIQUE NOT NULL,   -- '2010'
    cc_name          VARCHAR(100) NOT NULL,
    parent_id        UUID REFERENCES cost_centers(cc_id),
    cc_type          VARCHAR(20) NOT NULL,           -- PRODUCTION/SERVICE/ADMIN
    responsible_id   UUID,                           -- Manager responsable
    valid_from       DATE NOT NULL,
    valid_to         DATE,
    is_active        BOOLEAN DEFAULT TRUE
);

-- Profit Centers
CREATE TABLE profit_centers (
    pc_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pc_code          VARCHAR(10) UNIQUE NOT NULL,
    pc_name          VARCHAR(100) NOT NULL,
    business_area    VARCHAR(50),                    -- B2C / B2B / Internal
    responsible_id   UUID,
    is_active        BOOLEAN DEFAULT TRUE
);

-- Standard Costs por producto
CREATE TABLE product_standard_costs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id       UUID NOT NULL,
    valid_from       DATE NOT NULL,
    valid_to         DATE,
    material_cost    NUMERIC(18,4) NOT NULL,
    freight_cost     NUMERIC(18,4) DEFAULT 0,
    duty_cost        NUMERIC(18,4) DEFAULT 0,
    handling_cost    NUMERIC(18,4) DEFAULT 0,
    total_standard   NUMERIC(18,4) GENERATED ALWAYS AS
                     (material_cost + freight_cost + duty_cost + handling_cost) STORED,
    currency_code    CHAR(3) NOT NULL DEFAULT 'USD',
    status           VARCHAR(10) DEFAULT 'ACTIVE',
    released_by      UUID,
    released_at      TIMESTAMPTZ,
    UNIQUE(product_id, valid_from)
);

-- AP Open Items (Cuentas por Pagar abiertas)
CREATE TABLE vendor_open_items (
    item_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id        UUID NOT NULL,
    invoice_number   VARCHAR(50) NOT NULL,
    invoice_date     DATE NOT NULL,
    due_date         DATE NOT NULL,
    gross_amount     NUMERIC(18,2) NOT NULL,
    open_amount      NUMERIC(18,2) NOT NULL,     -- Reducido con pagos parciales
    currency_code    CHAR(3) NOT NULL,
    payment_terms_id UUID,
    po_id            UUID,                        -- Link al PO origen (3-way match)
    gr_id            UUID,                        -- Link al GR origen
    clearing_date    DATE,                        -- NULL = abierta
    clearing_doc_id  UUID,                        -- Payment run que la liquidó
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_voi_due_date    ON vendor_open_items(due_date) WHERE clearing_date IS NULL;
CREATE INDEX idx_voi_vendor      ON vendor_open_items(vendor_id) WHERE clearing_date IS NULL;

-- Budget
CREATE TABLE budget_versions (
    version_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_name     VARCHAR(50) NOT NULL,         -- '2026_APPROVED'
    fiscal_year      SMALLINT NOT NULL,
    status           VARCHAR(10) NOT NULL,          -- DRAFT/APPROVED/LOCKED
    approved_by      UUID,
    approved_at      TIMESTAMPTZ
);

CREATE TABLE budget_lines (
    line_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id       UUID REFERENCES budget_versions(version_id),
    fiscal_period    VARCHAR(7) NOT NULL,           -- '2026-05'
    gl_account_id    UUID REFERENCES gl_accounts(account_id),
    cost_center_id   UUID REFERENCES cost_centers(cc_id),
    profit_center_id UUID REFERENCES profit_centers(pc_id),
    budget_amount    NUMERIC(18,2) NOT NULL,
    currency_code    CHAR(3) NOT NULL DEFAULT 'USD'
);
```

---

## KPIs Financieros

| KPI | Fórmula | Target | Benchmark Industria |
|-----|---------|--------|---------------------|
| **Days Payable Outstanding (DPO)** | `(AP / COGS) × días` | 45-60 días | Manufacturing: 55 días |
| **Days Sales Outstanding (DSO)** | `(AR / Revenue) × días` | < 45 días | E-commerce B2B: 35 días |
| **Cash Conversion Cycle (CCC)** | `DSO + DIO - DPO` | < 30 días | E-commerce: 15-25 días |
| **Gross Profit Margin** | `(Revenue - COGS) / Revenue` | > 35% | Trading: 20-40% |
| **EBITDA Margin** | `EBITDA / Revenue` | > 15% | Software distribucion: 10-20% |
| **Close Cycle Time** | Días desde T+0 a reportes listos | ≤ 3 días | Best-in-class: 1 día |
| **AP Invoice Processing Cost** | USD por factura procesada | < $5 | Con automation: $2-3 |
| **Early Payment Discount Captured** | % de descuentos disponibles capturados | > 80% | Benchmark: 60-75% |
| **GL Reconciliation Rate** | % cuentas reconciliadas antes del día 3 | > 95% | Clase mundial: >99% |
| **Forecast Accuracy (Cash)** | `|Forecast - Actual| / Actual` | < 5% | Tesorería best practice: 3% |

---

## Roadmap de Implementación

```
Semana 1-2 (Quick Wins):
  ✅ FIN-02: Crear tabla gl_accounts con CoA 200 cuentas
  ✅ FIN-03: Posting periods table + validación en journal entries
  ✅ FIN-09: Cost centers hierarchy (Ventas/Ops/Tech/G&A)
  ✅ FIN-10: Profit centers básicos (B2C_AE / B2C_SA / Internal)

Semana 3-5 (Core Financiero):
  ✅ FIN-01: Universal Journal (financial_entries table)
  ✅ FIN-08: Bank reconciliation import + auto-match
  ✅ FIN-04: AP Aging Report automático
  ✅ FIN-05: Payment Run básico (manual approval required)
  ✅ FIN-15: P&L real-time view materializada
  ✅ FIN-16: Balance Sheet reconciliation automática

Semana 6-8 (Reporting & Control):
  ✅ FIN-11: Standard cost por SKU + validez temporal
  ✅ FIN-12: Price variance posting en GR
  ✅ FIN-14: Period Close Checklist automatizada (Celery Beat)
  ✅ FIN-19: UAE CIT provisioning automático
  ✅ FIN-20: FX Revaluation al cierre
  ✅ FIN-21: Journal Entry approval workflow (SoD)

Semana 9-12 (Analytics & Planning):
  ✅ FIN-13: CO-PA contribution margin vista
  ✅ FIN-17: Cash Flow Statement método indirecto
  ✅ FIN-18: 13-week cash forecast
  ✅ FIN-22: Budget vs Actual dashboard
  ✅ FIN-06: Early payment discount capture
```

---

## Encadenamiento Cross-Module

### Entradas a Finanzas (desde módulos anteriores)

| Módulo Origen | ID | Mejora | Impacto en Finanzas |
|--------------|-----|--------|---------------------|
| **Billing** | BIL-05 | FI-SD journal entry automático | → `financial_entries` con DR AR / CR Revenue / CR Tax |
| **Billing** | BIL-07 | Revenue recognition (ASC 606) | → Diferir revenue → FIN-15 P&L correcto |
| **Billing** | BIL-11 | Dunning automation | → AR open items → FIN-04 AP Aging (espejo en AR) |
| **Compras** | PRC-17 | Three-way match → Invoice posting | → `vendor_open_items` → FIN-04 AP Aging → FIN-05 Payment Run |
| **Compras** | PRC-11 | PIR — Vendor price agreed | → FIN-12 Price variance: PO price vs. standard |
| **Inventario** | INV-03 | AVCO/FIFO cost per lot | → FIN-11 Standard cost input; valuation base |
| **Inventario** | INV-24 | Cycle count ajustes | → Journal entry: DR/CR Inventory Adjustment Account |
| **Pricing** | PRI-18 | Daily FX rates | → FIN-20 FX Revaluation al cierre de mes |
| **Ventas** | VEN-09 | Credit check → AR balance | → FIN-16 AR reconciliation |

### Salidas de Finanzas (hacia otros módulos o usuarios)

| Destino | Qué entrega Finanzas |
|---------|---------------------|
| **CFO / Dirección** | FIN-15 P&L, FIN-17 Cash Flow, FIN-18 Forecast, FIN-22 Budget vs Actual |
| **Compras** | FIN-05 Payment Run → confirmación de pago al proveedor → cierra ciclo P2P |
| **Ventas** | FIN-19 UAE CIT → impacta pricing si margen bajo. FIN-10 PC margin → decisiones de canal |
| **Inventario** | FIN-11 Standard Cost → base para FIN-12 varianzas y para reporting de inventory value |
| **Auditoría / Fiscal** | FIN-21 Journal audit trail, FIN-03 closed periods → inmutabilidad del registro |

---

## Resumen: 154 + 22 = **176 Mejoras Totales Documentadas**

| Módulo | Mejoras | Archivo |
|--------|---------|---------|
| Maestros | 47 | `technical-erp-master-data-mejores-practicas-industria-research-2026-05-13.md` |
| Inventario | 25 | `technical-erp-inventario-mejores-practicas-research-2026-05-13.md` |
| Compras | 23 | `technical-erp-compras-mejores-practicas-research-2026-05-13.md` |
| Pricing | 18 | `technical-erp-pricing-mejores-practicas-research-2026-05-13.md` |
| Ventas | 21 | `technical-erp-ventas-mejores-practicas-research-2026-05-13.md` |
| Billing | 20 | `technical-erp-billing-mejores-practicas-research-2026-05-13.md` |
| **Finanzas** | **22** | **`technical-erp-finanzas-mejores-practicas-research-2026-05-13.md`** |
| **TOTAL** | **176** | |

---

**Flujo completo documentado:**
Maestros ✅ → Inventario ✅ → Compras ✅ → Pricing ✅ → Ventas ✅ → Billing ✅ → **Finanzas ✅**

**El ciclo ERP completo está cubierto.**
