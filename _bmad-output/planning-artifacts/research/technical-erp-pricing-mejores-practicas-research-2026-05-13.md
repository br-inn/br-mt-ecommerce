---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowType: 'research'
research_type: 'technical'
research_topic: 'ERP Pricing — mejores prácticas de la industria'
user_name: 'psierra'
date: '2026-05-13'
---

# Research Report: ERP Pricing — Mejores Prácticas

**Flujo:** Maestros ✅ → Inventario ✅ → Compras ✅ → **Pricing** → Ventas → Billing → Finanzas

---
## Módulo 1 — Condition Technique (SAP SD) — El Motor de Precios

El pricing en SAP no guarda un precio en el producto. Usa una **técnica de condiciones** que resuelve el precio correcto en el momento de crear una orden de venta, buscando de lo más específico a lo más general.

### Componentes y su relación

```
Condition Table  → define las "llaves" de búsqueda (ej: Customer + Material)
      │
Access Sequence  → orden de búsqueda de más específico a más general
      │
Condition Type   → qué calcula: precio base (PR00), descuento (K007), flete (KF00), IVA (MWST)
      │
Condition Record → el valor real con validez (amount, %, from_date, to_date, currency)
      │
Pricing Procedure → secuencia de condition types que se suman/restan = precio final
```

### Ejemplo real de resolución de precio

```
Orden de venta: Cliente MT-Dubai, Producto SKU-001, Qty 100 unidades

Pricing Procedure ejecuta en secuencia:
  PR00  → precio base       = busca por: Customer+Material → no encontrado
                              → busca por: Material+SalesOrg → USD 50.00 ✓
  K007  → descuento cliente = busca por: Customer → 5% ✓
  KF00  → flete            = busca por: ShipTo+Weight → USD 3.00/kg ✓
  MWST  → IVA              = busca por: TaxClass(producto)+TaxClass(cliente) → 5% UAE VAT ✓

Precio final = 50.00 − (50.00×5%) + 3.00×peso + IVA
             = 47.50 + flete + 5% UAE VAT
```

**Beneficio clave:** el mismo producto puede tener precios completamente diferentes para cada cliente, canal, cantidad y fecha — sin tocar el maestro de producto.

_Fuente: [SAP Press — Condition Technique](https://blog.sap-press.com/what-is-the-condition-technique-in-sap) · [KaarTech — SAP SD Pricing Procedure](https://www.kaartech.com/blogs/sap-sales-distribution-sap-sd-pricing-procedure/) · [IT Pathshaala — Condition Type & Access Sequence](https://itpathshaala.com/tutorials/sap-sd/condition-type-and-access-sequence.html)_

---

## Módulo 2 — Price Lists y Pricing por Segmento de Cliente

### Arquitectura de Pricelists

El estándar de industria organiza los precios en **capas jerárquicas**:

```
Nivel 1 — List Price (precio catálogo público)
      │
      ▼
Nivel 2 — Customer Group Price (precio por segmento: Distribuidor / Retail / Gobierno)
      │
      ▼
Nivel 3 — Contract Price (precio negociado con este cliente específico)
      │
      ▼
Nivel 4 — Volume Discount (descuento adicional por cantidad en esta orden)
      │
      ▼
Nivel 5 — Promotional Price (precio temporal de campaña)
```

El sistema aplica **la capa más específica que encuentre vigente**. Un cliente con contrato ve su precio de contrato; uno sin contrato ve el precio de su segmento.

**Regla de industria:** 1 pricelist por tier de cliente + 1 por contrato especial. Una empresa B2B típica con 5 tiers y 20 contratos = 25 pricelists. Nunca 1 pricelist por cliente — no escala.

_Fuente: [Ecosire — Customer-Specific Pricing](https://ecosire.com/blog/customer-specific-pricing-tiered-discounts) · [Koblesystems — Setting Prices with ERP](https://koblesystems.com/blog/setting-and-changing-prices-with-an-erp)_

---

## Módulo 3 — Volume Discounts y Escala de Precios

### Dos modelos de descuento por volumen

**Modelo A — Bracket (todo al precio del tier alcanzado):**
```
Qty  1-49   → $50.00/u
Qty  50-99  → $45.00/u  ← si pides 60: TODAS las unidades a $45
Qty 100+    → $40.00/u
```

**Modelo B — Incremental (solo las unidades del tier):**
```
Qty  1-49   → $50.00/u  ← las primeras 49 a $50
Qty 50-99   → $45.00/u  ← las siguientes 50 a $45
Qty 100+    → $40.00/u  ← las siguientes a $40
```

El Modelo A es el más común en B2B (más simple, fácil de comunicar). El Modelo B protege mejor el margen.

**En SAP:** ambos se implementan con **Scale Basis** en el condition record. `Scale Type A` = bracket. `Scale Type B` = incremental.

_Fuente: [Wantek — Volume Discount Formula](https://www.iwantek.com/blogs/news/volume-discount-pricing-formula-tiered-calculation-steps) · [DealHub — Volume Pricing](https://dealhub.io/glossary/volume-pricing/) · [Rockton — Tiered Pricing 2025](https://erpsoftwareblog.com/2025/11/understanding-tiered-pricing-rockton-software/)_

---

## Módulo 4 — Tipos de Condition Types (Catálogo de Cargos y Descuentos)

Los sistemas ERP modularizan el precio en **condition types** independientes y acumulables:

| Tipo | Código SAP | Qué es | Cómo se calcula |
|------|-----------|--------|----------------|
| **Precio base** | PR00 | Precio de lista del producto | Fijo por currency |
| **Descuento cliente** | K007 | Descuento negociado con cliente | % sobre precio base |
| **Descuento material** | K004 | Descuento por producto específico | % o monto fijo |
| **Descuento volumen** | K029 | Escala por cantidad | Scale: qty → % |
| **Descuento campaña** | KA00 | Promoción temporal | % con from/to date |
| **Recargo por urgencia** | ZUG1 | Express / rush fee | Monto fijo o % |
| **Flete** | KF00 | Costo de envío | Peso × tarifa / zona |
| **Seguro** | ZSEG | Cargo de seguro de transporte | % sobre valor |
| **Impuesto (IVA/VAT)** | MWST | Impuesto indirecto | % según país/cliente |
| **Retención** | ZRet | Retención en fuente (LATAM) | % sobre base imponible |

**Principio:** el precio final es la suma algebraica de todos los condition types de la pricing procedure. Cada uno puede activarse/desactivarse según el contexto del documento.

---

## Módulo 5 — Tax Determination

### El Patrón SAP de Determinación de Impuestos

El impuesto correcto no se hardcodea — se determina en base a 3 factores:

```
Tax = f(
    TaxClassification(Producto),   → si el producto es gravado, exento, o tasa reducida
    TaxClassification(Cliente),    → si el cliente es contribuyente, exento, gobierno
    PlantCountry / ShipToCountry   → la jurisdicción fiscal aplica el porcentaje
)
```

**Para UAE (el mercado principal del programa MT):**
- VAT rate: 5% estándar (Federal Decree-Law No. 8 of 2017)
- Exportaciones: 0% (zero-rated)
- Sectores específicos (salud, educación): exentos
- El sistema debe guardar el TRN (Tax Registration Number) del cliente

**Para LATAM (México, Colombia, etc.):**
- IVA variable por país (16% MX, 19% CO)
- Retenciones en la fuente (cliente retiene un % del IVA y lo paga directamente al fisco)
- Percepción IVA en algunos países (el vendedor retiene por cuenta del comprador)

**Best practice para multi-país:** usar un **tax engine** externo (Avalara, Vertex) conectado al ERP vía API. El ERP envía los parámetros de la transacción; el engine devuelve el impuesto exacto + el jurisdiction code. Esto evita mantener tablas de impuestos internamente.

_Fuente: [SAP Learning — Tax Determination](https://learning.sap.com/courses/configuring-pricing-in-sap-s-4hana-sales/analyzing-the-determination-of-taxes) · [Avalara — SAP Tax Integration](https://www.avalara.com/us/en/products/integrations/sap/sap-clouderp-private-and-sap-ecc.html)_

---

## Módulo 6 — Multi-Moneda

### Arquitectura de Monedas en ERP

```
Transaction Currency  → Moneda del documento (USD, AED, MXN)
      │
      ↓ conversión por tipo de cambio vigente
      │
Company Code Currency → Moneda funcional de la empresa (ej: USD)
      │
      ↓ conversión adicional si es grupo multinacional
      │
Group Currency        → Moneda de consolidación del grupo (ej: USD)
```

**Tipos de cambio:**
- **Spot rate:** tipo del día (para transacciones spot)
- **Average rate:** promedio del mes (para revaluaciones mensuales)
- **Historical rate:** tipo al momento de la transacción original (para comparaciones)

**Best practices de NetSuite:**
- Actualizar tipos de cambio diariamente desde un provider externo (Xignite, ECB)
- Revaluación mensual de saldos open en moneda extranjera → diferencias de cambio a cuenta de resultado
- Precio de venta en moneda del cliente; contabilización siempre en moneda funcional

_Fuente: [NetSuite — Multi-Currency Accounting](https://www.netsuite.com/portal/resource/articles/accounting/multi-currency-accounting.shtml) · [Emphorasoft — NetSuite Multi-Currency Best Practices](https://emphorasoft.com/best-practices-for-managing-multi-currency-transactions-in-netsuite/)_

---

## Módulo 7 — Pricing B2B vs B2C

| Dimensión | B2C (consumidor final) | B2B (empresa compradora) |
|-----------|----------------------|------------------------|
| **Precio visible** | Precio público en catálogo | Precio negociado — invisible al resto |
| **Descuentos** | Cupones, promociones temporales | Contratos, volumen, rebates |
| **Aprobación de precio** | Automática | Puede requerir cotización formal |
| **Multi-nivel** | Raro (precio simple) | Frecuente (precio base + descuento contrato + rebate) |
| **Moneda** | Moneda local | Multi-moneda según país del comprador |
| **Impuesto** | Precio con impuesto incluido (MSRP) | Precio neto + impuesto desglosado |
| **Freight** | Gratuito sobre mínimo o fijo | Calculado por peso/zona/incoterm |

_Fuente: [Shopify — B2B Pricing Strategy 2025](https://www.shopify.com/enterprise/blog/b2b-pricing-strategy) · [SAP — Guide to B2B Pricing Strategies](https://www.sap.com/resources/b2b-pricing-strategies) · [Hybrismart — B2B Pricing in E-Commerce](https://hybrismart.com/2025/02/23/customer-specific-pricing-and-availability-in-b2b-e-commerce/)_

---

## Mejoras Aplicables al Sistema — Pricing

> Encadena con: Maestros (product + vendor pricing) → Compras (PIR price) → Ventas (precio en SO) → Billing (precio en factura).

---

### PRI-1 — Condition Technique

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-01 | **Engine de pricing basado en condition types y access sequences** | SAP SD Condition Technique | Alta | Tablas: `condition_types` (code, calculation_type: %, amount, qty_scale) + `access_sequences` (priority, key_fields[]) + `condition_records` (keys, value, valid_from, valid_to). Engine Python resuelve en orden |
| PRI-02 | **Pricing procedure: secuencia configurable de condition types** | SAP Pricing Procedure | Alta | Tabla `pricing_procedures` con `steps[]` (condition_type, from_step, to_step, condition_basis, print_flag). El precio final = suma algebraica de todos los steps |
| PRI-03 | **Resolución de precio de más específico a más general** | SAP Access Sequence | Alta | Por cada condition type, buscar: Customer+Product → Customer+Category → CustomerGroup+Product → Product → catch-all. Retornar el primero que coincida |

---

### PRI-2 — Price Lists y Segmentos

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-04 | **Pricelists por segmento de cliente con herencia** | Industry pricelist pattern | Alta | Tabla `price_lists` (name, customer_group_id, valid_from, valid_to, currency). `price_list_items` (price_list_id, product_id, price). Herencia: si no encuentra en pricelist del cliente, sube al group pricelist |
| PRI-05 | **Precio específico por cliente (override de pricelist)** | SAP K007 customer discount | Alta | `customer_specific_prices` (customer_id, product_id, price, valid_from, valid_to). Tiene prioridad sobre la pricelist del segmento |
| PRI-06 | **Validez temporal en todos los condition records** | SAP validity period | Alta | Todos los precios y descuentos tienen `valid_from` y `valid_to`. El engine solo usa registros vigentes a la fecha del documento. Historial de precios completo |

---

### PRI-3 — Descuentos por Volumen

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-07 | **Escala de precios por cantidad (bracket y incremental)** | SAP Scale Type A/B | Alta | Tabla `price_scales` (condition_record_id, from_qty, to_qty, price_or_pct). El engine selecciona el tier correcto según la qty de la orden |
| PRI-08 | **Escala de precios por monto de orden** | SAP order value scale | Media | Descuento activado cuando el valor total de la orden supera un threshold. Ej: 3% de descuento si orden > $5,000 |

---

### PRI-4 — Tipos de Cargo

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-09 | **Condition types para flete calculado automáticamente** | SAP KF00 | Media | `freight_zones` (from_country, to_country, carrier) + `freight_rates` (zone_id, weight_from, weight_to, rate). El engine calcula flete al conocer el peso del pedido y zona de destino |
| PRI-10 | **Condition types para recargos configurables** | SAP surcharge conditions | Media | Recargos: express fee, hazardous materials, cold chain, minimum order surcharge. Cada uno como condition type activable/desactivable por regla |
| PRI-11 | **Precio promocional con from/to date y prioridad** | SAP KA00 promotional | Alta | Condition record con `promotion_id`, `valid_from`, `valid_to`, prioridad mayor que precio base. Al expirar la promoción: el precio vuelve automáticamente al base |

---

### PRI-5 — Impuestos

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-12 | **Tax classification en producto y cliente** | SAP tax class | Alta | Ya identificado en M3-04. En pricing: `product.tax_class` (STANDARD / EXEMPT / REDUCED) + `customer.tax_class` (TAXABLE / EXEMPT / GOVERNMENT). La intersección determina la tasa |
| PRI-13 | **Tabla de tasas de impuesto por país + categorías** | SAP tax procedure | Alta | `tax_rates` (country_code, tax_class_product, tax_class_customer, rate_pct, valid_from, valid_to). Para UAE: 5% / 0% / exento. Para MX: 16% / 0%. Sin hardcode |
| PRI-14 | **Desglose de impuesto en documento (tax_amount separado)** | SAP tax posting | Alta | En SO y factura: `subtotal`, `discount_total`, `freight`, `tax_base`, `tax_amount`, `total`. El impuesto nunca está embebido en el precio del producto |
| PRI-15 | **Integración con tax engine externo (Avalara / Vertex) vía API** | SAP + Avalara | Baja | Para escenarios multi-jurisdicción complejos. El ERP envía parámetros; el engine devuelve el monto exacto. Considerar cuando se expanda a >5 países |

---

### PRI-6 — Multi-Moneda

| # | Mejora | Inspiración | Prioridad | Notas |
|---|--------|------------|-----------|-------|
| PRI-16 | **Tabla de tipos de cambio con actualización diaria** | NetSuite exchange rates | Alta | `exchange_rates` (from_currency, to_currency, rate_type: SPOT/AVG/HIST, rate, valid_date). El engine convierte automáticamente. Source: ECB/Fixer.io API vía Celery Beat diario |
| PRI-17 | **Precio de venta en moneda del cliente; contabilización en moneda funcional** | NetSuite multi-currency | Alta | SO en moneda del cliente. Al contabilizar: convertir a USD (moneda funcional) al tipo del día. Diferencia de cambio al cobrar: a cuenta `exchange_gain_loss` |
| PRI-18 | **Revaluación mensual de saldos en moneda extranjera** | NetSuite revaluation | Media | Job Celery al cierre de mes: recalcular saldos abiertos (AR/AP en moneda ext.) al tipo promedio del mes. Diferencia → `unrealized_fx_gain_loss` |

---

## Executive Summary — Pricing

### Los 5 Principios de Pricing de la Industria

1. **El precio nunca está en el producto** — El producto tiene un precio de lista; el precio real de venta lo resuelve el engine en el momento de la orden, consultando condiciones por cliente, canal, cantidad y fecha. Esto es la condition technique.

2. **Pricelists por segmento, no por cliente** — 25 pricelists bien diseñadas cubren a 10,000 clientes. Una pricelist por cliente no escala y crea caos de mantenimiento.

3. **La escala de volumen es una inversión, no un regalo** — Los descuentos por volumen deben estar anclados al costo. El promedio B2B pierde 2-5% de margen bruto por descuentos no controlados (McKinsey).

4. **El impuesto es un dato de contexto, no un campo del producto** — El mismo producto puede ser gravado al 5%, al 0% o exento, dependiendo del cliente y el país de destino. El tax engine resuelve esto en runtime.

5. **Multi-moneda desde el día uno** — Si el sistema no soporta múltiples monedas nativamente, se paga una deuda técnica enorme al internacionalizarse. Tipos de cambio automáticos, revaluación mensual, y desglose de diferencia de cambio son no-negociables en un ERP serio.

---

### Mapa de Mejoras Consolidado — Pricing

| ID | Mejora | Prioridad | Complejidad |
|----|--------|-----------|-------------|
| PRI-01 | Engine condition technique | Alta | Alta |
| PRI-02 | Pricing procedure configurable | Alta | Alta |
| PRI-03 | Resolución más específico → general | Alta | Media |
| PRI-04 | Pricelists por segmento con herencia | Alta | Media |
| PRI-05 | Precio específico por cliente | Alta | Baja |
| PRI-06 | Validez temporal en condition records | Alta | Baja |
| PRI-07 | Escala de precios por cantidad | Alta | Media |
| PRI-08 | Escala por monto de orden | Media | Baja |
| PRI-09 | Flete calculado automáticamente | Media | Media |
| PRI-10 | Recargos configurables | Media | Baja |
| PRI-11 | Precio promocional temporal | Alta | Baja |
| PRI-12 | Tax class producto + cliente | Alta | Baja |
| PRI-13 | Tabla tasas de impuesto por país | Alta | Baja |
| PRI-14 | Desglose impuesto en documento | Alta | Baja |
| PRI-15 | Integración tax engine externo | Baja | Alta |
| PRI-16 | Tipos de cambio con update diario | Alta | Media |
| PRI-17 | Precio en moneda cliente / contab. funcional | Alta | Media |
| PRI-18 | Revaluación mensual moneda extranjera | Media | Baja |

**Total: 18 mejoras identificadas para el módulo de Pricing**

---

### Encadenamiento

```
COMPRAS ─────────────────────────────────────────────────────
  PIR price (PRC-11)      → es un condition record de compra
  Contract prices (PRC-09)→ se reflejan como condition records de compra

VENTAS (siguiente módulo) ──────────────────────────────────
  SO creation             → llama al pricing engine (PRI-01/02/03)
  Customer pricelist      → resolución PRI-04/05
  Tax on SO               → PRI-12/13/14
  Currency on SO          → PRI-16/17

BILLING ─────────────────────────────────────────────────────
  Invoice pricing         → copia el pricing del SO (no recalcula)
  Tax on invoice          → mismo desglose que el SO
```

---

## Sources

- [SAP Press — Condition Technique](https://blog.sap-press.com/what-is-the-condition-technique-in-sap)
- [KaarTech — SAP SD Pricing Procedure](https://www.kaartech.com/blogs/sap-sales-distribution-sap-sd-pricing-procedure/)
- [Ecosire — Customer-Specific Pricing](https://ecosire.com/blog/customer-specific-pricing-tiered-discounts)
- [Wantek — Volume Discount Formula](https://www.iwantek.com/blogs/news/volume-discount-pricing-formula-tiered-calculation-steps)
- [DealHub — Volume Pricing](https://dealhub.io/glossary/volume-pricing/)
- [Shopify — B2B Pricing Strategy 2025](https://www.shopify.com/enterprise/blog/b2b-pricing-strategy)
- [SAP — B2B Pricing Strategies](https://www.sap.com/resources/b2b-pricing-strategies)
- [SAP Learning — Tax Determination](https://learning.sap.com/courses/configuring-pricing-in-sap-s-4hana-sales/analyzing-the-determination-of-taxes)
- [Avalara — SAP Tax Integration](https://www.avalara.com/us/en/products/integrations/sap/sap-clouderp-private-and-sap-ecc.html)
- [NetSuite — Multi-Currency Accounting](https://www.netsuite.com/portal/resource/articles/accounting/multi-currency-accounting.shtml)
- [Emphorasoft — NetSuite Multi-Currency Best Practices](https://emphorasoft.com/best-practices-for-managing-multi-currency-transactions-in-netsuite/)
- [Hybrismart — B2B Pricing E-Commerce](https://hybrismart.com/2025/02/23/customer-specific-pricing-and-availability-in-b2b-e-commerce/)

---

**Completion Date:** 2026-05-13 · **Total mejoras:** 18 · **Fuentes:** 12
**Siguiente módulo:** Ventas / Order-to-Cash (O2C)
