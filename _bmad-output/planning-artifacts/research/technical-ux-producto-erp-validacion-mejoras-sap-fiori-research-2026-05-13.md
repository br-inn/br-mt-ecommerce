---
stepsCompleted: [1, 2, 3, 4, 5, 6]
workflowType: 'research'
research_type: 'technical'
research_topic: 'UX Producto ERP — Validación y Mejoras vs SAP Fiori / Akeneo / Industry'
user_name: 'psierra'
date: '2026-05-13'
---

# Research Report: UX Producto ERP — Validación y Gap Analysis vs SAP Fiori / Akeneo

---

## 1. Auditoría del Estado Actual (br-mt-ecommerce)

### Estructura de la Página de Producto

```
/catalogo/[sku]
  └── Layout:
        ← Back
        ProductHeader
          ├── SKU (mono)           ← familia badge
          ├── active/inactive badge (BINARIO)
          ├── Nombre producto
          ├── DataQuality badge
          ├── TranslationStatus pills (en/es/ar)
          └── [Edit] [⋮ Actions menu]
        ProductTabs
          Specs | Imágenes | Traducciones | Costos | Datasheets | Recambios | Audit
        Tab content (children)
```

### Tabs Actuales

| Tab | Contenido | Ruta |
|-----|-----------|------|
| **Specs** | DN/PN/Material/Tipo/Conexión/Peso/Dim + Empaque + EAV + Tablas | `/catalogo/[sku]` |
| **Imágenes** | Galería assets (photo/banner/drawing) | `/imagenes` |
| **Traducciones** | ES / AR multiidioma | `/traducciones` |
| **Costos** | Cost engine del producto | `/costos` |
| **Datasheets** | PDFs técnicos | `/datasheets` |
| **Recambios** | Compatibilidades M:N | `/recambios` |
| **Audit** | Log de cambios | `/audit` |

### Gaps M1 Detectados

| Mejora M1 | Gap en UX actual |
|-----------|-----------------|
| **M1-01** ProductRelease por mercado | ❌ No existe tab "Mercados" — la tabla `product_releases` se creó pero no tiene UI |
| **M1-04** UoM base + conversiones | ❌ No se muestra `base_uom` ni conversiones UoM en ningún tab |
| **M1-05** Lifecycle in_review | ⚠️ Se muestra como binario `active/inactive` — no refleja `draft/in_review/discontinued` |
| **M1-08** GTIN/EAN | ❌ Solo EAN en el campo `packaging.ean_unit` — no hay campo `gtin` global visible |

---

## 2. Referencia SAP Fiori — Material Master (Object Page)

### Patrón Object Page

SAP Fiori usa el **Object Page Floorplan** como patrón estándar para maestros de datos. Sus principios clave:

```
┌─────────────────────────────────────────────────────────────────┐
│  OBJECT HEADER                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ [Image]  Nombre objeto              [Status Badge]       │  │
│  │          Subtítulo (ID/SKU)         [Edit] [Copy] [...]  │  │
│  │          ─────────────────────────────────────────────── │  │
│  │  KVP1: Valor   KVP2: Valor   KVP3: Valor   KVP4: Valor  │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  [General] [Purchasing] [MRP] [Plant Data] [Sales] [Accounting] │
├─────────────────────────────────────────────────────────────────┤
│  TAB CONTENT                                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Key Value Pairs en el Header (SAP Object Page)

SAP Fiori muestra 4-6 KVPs directamente en el header. Para Material Master:
- Base Unit of Measure
- Material Group  
- Plant
- Valuation Class

**Principio clave**: el header responde la pregunta "¿Qué es este objeto?" sin entrar a ningún tab.

### Tabs del Material Master SAP S/4HANA 2025

| Tab | Datos clave |
|-----|------------|
| **General Data** | Descripción, UoM base, peso, dimensiones, HS code |
| **Purchasing** | Grupo compras, precio pedido, UoM compra, tolerancias |
| **MRP** | Método, punto reorden, stock seguridad, lead time |
| **Plant Data / Warehouse** | Stock actual, ubicación, movimientos |
| **Sales: General** | Grupo material, jerarquía producto, estado ventas |
| **Sales: Plant Data** | Estrategia entrega, disponibilidad, UoM ventas |
| **Accounting** | Valoración, precio estándar, clase de valoración |
| **Costing** | Costo estándar, sheet de costos |
| **Classification** | Clase + características tipadas (EAV) |

**Principio clave**: cada tab = una "vista de rol" (comprador / almacén / finanzas). El diseño es role-based.

### Status Badge SAP Fiori

SAP Fiori usa **Semantic Colors** para el estado:
```
● Active      → Verde (Success)
● In Review   → Naranja/Amarillo (Warning)  
● Draft       → Gris (Neutral)
● Discontinued → Rojo (Error/Negative)
● Deprecated  → Naranja (Critical)
```

_Fuente: [SAP Fiori Design Guidelines](https://experience.sap.com/fiori-design-web/) · [Object Page Floorplan](https://experience.sap.com/fiori-design-web/object-page/)_

---

## 3. Referencia Akeneo PIM — Product Page

### Layout Akeneo

```
┌──────────────────────────────────────────────────────────────────┐
│  Completeness Ring  │  Nombre producto  │  [Channel selector]   │
│  [████░░░]  72%     │  SKU              │  [Locale selector]    │
│  Quality: B         │                   │                        │
├──────────────────────────────────────────────────────────────────┤
│  [Attributes] [Categories] [Associations] [History]             │
├───────────────────────┬──────────────────────────────────────────┤
│  ATTRIBUTE GROUPS     │  FORM                                    │
│  ● General (4/6) ✓   │  Product Name *                         │
│  ● Marketing (2/4)   │  ┌────────────────────────────────────┐  │
│  ● Technical (8/8) ✓ │  │ [EN] [ES] [AR]  channel tabs       │  │
│  ● Media (1/3)       │  └────────────────────────────────────┘  │
└───────────────────────┴──────────────────────────────────────────┘
```

### Patrones Akeneo a adoptar

| Patrón | Descripción | Valor |
|--------|-------------|-------|
| **Completeness ring** | % de campos completos por canal/locale | Visibilidad inmediata de calidad |
| **Quality grade A/B/C/D** | Calificación visible en listado y detalle | Priorización de esfuerzo |
| **Channel/locale toggle** | Switch de mercado en el header | Un producto, múltiples contextos |
| **Attribute group panel** | Panel izquierdo con grupos de atributos y progreso por grupo | Orientación al editor |
| **Completeness per group** | `(4/6)` junto a cada grupo de atributos | Claridad sobre qué falta |
| **Inline save** | Guardar campo individual sin full form submit | Velocidad de edición |

_Fuente: [Akeneo UX Design Philosophy](https://www.akeneo.com/blog/ux-design-part-1/) · [Akeneo Completeness](https://help.akeneo.com/serenity-your-first-steps-with-akeneo/serenity-understand-product-completeness)_

---

## 4. Referencia D365 — Released Product (M1-01)

### Concepto Released Product

D365 separa visualmente el producto en dos niveles:

```
PRODUCT DEFINITION (global)         RELEASED PRODUCT (per legal entity)
─────────────────────────────       ──────────────────────────────────────
• SKU / Product number              • Legal entity: UAE / KSA / MX
• Product name                      • Sales price, currency
• Product group / Category          • Purchase price
• Unit of measure (base)            • Item model group (FIFO/AVCO)
• GTIN                              • Sales tax group
• Product dimensions                • Warehouse / location defaults
                                    • Item coverage group (MRP)
```

**UX D365**: el botón "Release product" en la vista global abre un wizard para seleccionar entidades legales y configurar los parámetros locales. Después aparece en la lista de Released Products por entidad.

---

## 5. Gap Analysis — Tabla de Mejoras UX

| # | Área | Gap Actual | Patrón de Referencia | Mejora Propuesta | Prioridad |
|---|------|-----------|---------------------|-----------------|-----------|
| **UX-01** | Header — Status | Badge binario `active/inactive` | SAP Fiori Semantic Colors | `LifecycleStatusBadge` con colores: draft=gris, in_review=amarillo, active=verde, discontinued=rojo | 🔴 CRÍTICA |
| **UX-02** | Header — Quick Facts | Solo nombre y familia | SAP Fiori KVP row | Fila de 4 KVPs: UoM Base · GTIN · Brand · Lifecycle | 🟠 ALTA |
| **UX-03** | Tabs — Mercados | No existe | D365 Released Product / SAP Sales Org | Tab "Mercados" — tabla de product_releases con precio local, moneda, impuesto, activación por mercado | 🔴 CRÍTICA |
| **UX-04** | Tabs — Unidades | No existe | SAP MM UoM alternativas | Tab "Unidades" — base_uom + tabla de conversiones (BOX→UNIT factor) | 🟠 ALTA |
| **UX-05** | Specs — GTIN | Solo EAN en packaging | GS1 estándar | Campo GTIN en card de Identidad/Global + validación visual EAN-13 | 🟠 ALTA |
| **UX-06** | Header — Completeness | DataQuality badge (text) | Akeneo completeness ring | Ring de progreso % con tooltip mostrando campos faltantes por grupo | 🟡 MEDIA |
| **UX-07** | Listado — Lifecycle | Columna `active` boolean | SAP Fiori status column | Columna lifecycle_status con chip de color en products-table | 🟠 ALTA |
| **UX-08** | Breadcrumb | Solo "← Back" | SAP Fiori/Akeneo breadcrumb | `Catálogo > SKU > Tab` navegable | 🟡 MEDIA |
| **UX-09** | Header — Inline Edit | Navega a `/edit` page separada | Akeneo inline mode | Toggle Edit/View inline en el detalle sin cambiar de página | 🟡 MEDIA |
| **UX-10** | Mercados — Activate | No existe | D365 "Release product" button | Botón "Activar para este mercado" con confirmación | 🔴 CRÍTICA |

---

## 6. Arquitectura de Implementación UX

### Tab "Mercados" — Referencia D365/SAP

```
┌──────────────────────────────────────────────────────────────────────┐
│  MERCADOS / RELEASES                           [+ Agregar Mercado]  │
├─────────────┬────────────────┬─────────┬──────┬──────────┬──────────┤
│  Mercado    │  Nombre local  │  Precio │  FX  │  Clase   │  Estado  │
├─────────────┼────────────────┼─────────┼──────┼──────────┼──────────┤
│  🇦🇪 UAE    │  كرسي مريح    │  450 AED│  —   │  VAT_5   │  ● Active│
│  🇸🇦 KSA    │  كرسي مكتب   │  480 SAR│  —   │  VAT_15  │  ● Active│
│  🇲🇽 MX     │  Silla ergon. │  —      │  —   │  IVA_16  │  ○ Draft │
└─────────────┴────────────────┴─────────┴──────┴──────────┴──────────┘
```

### LifecycleStatusBadge — Semantic Colors

```tsx
const LIFECYCLE_CONFIG = {
  draft:        { label: "Borrador",   color: "secondary",    dot: "bg-gray-400"   },
  in_review:    { label: "En Revisión",color: "warning",      dot: "bg-yellow-500" },
  active:       { label: "Activo",     color: "success",      dot: "bg-green-500"  },
  deprecated:   { label: "Obsoleto",   color: "outline",      dot: "bg-orange-500" },
  replaced:     { label: "Reemplazado",color: "outline",      dot: "bg-orange-400" },
  discontinued: { label: "Discontinuado", color: "destructive", dot: "bg-red-500" },
}
```

### Header Quick Facts — Inspirado en SAP Fiori KVPs

```tsx
// Fila de 4 KVPs debajo del nombre (SAP Object Page pattern)
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 rounded-lg border bg-muted/30 p-3">
  <KVP label="UoM Base"  value={product.base_uom ?? "UNIT"} />
  <KVP label="GTIN"      value={product.gtin ?? "—"} mono />
  <KVP label="Marca"     value={product.brand ?? "—"} />
  <KVP label="Serie"     value={product.series ?? "—"} />
</div>
```

---

## 7. Roadmap de Implementación UX

```
Sprint actual (implementar hoy):
  ✅ UX-01: LifecycleStatusBadge en ProductHeader
  ✅ UX-03: Tab "Mercados" + MercadosClient (tabla releases)
  ✅ UX-04: Tab "Unidades" + UnidadesClient (base_uom + conversiones)
  ✅ UX-05: GTIN en ProductSpecs card
  ✅ UX-07: lifecycle_status chip en products-table
  ✅ UX-02: Quick Facts row en ProductHeader

Próximo sprint:
  ○ UX-06: Completeness ring (requiere API de completeness por familia)
  ○ UX-08: Breadcrumb componente
  ○ UX-09: Inline edit mode
  ○ UX-10: "Activar mercado" wizard multi-step
```
