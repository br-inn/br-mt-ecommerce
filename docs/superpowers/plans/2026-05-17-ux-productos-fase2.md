# UX Productos Fase 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir vista galería, quick edit desde tabla, navegación prev/next en detalle, badge hasImage dinámico en tabs, "Revisión de calidad" como vista guardada y URLs compartibles para vistas.

**Architecture:** Tres workstreams independientes que pueden ejecutarse en paralelo. A2 toca `page.tsx` y el drawer de edición. B2 toca el layout del detalle y el header. C2 toca el sistema de vistas guardadas.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4, TanStack Query, Lucide React, Shadcn/ui Sheet, nuqs, sessionStorage, navigator.clipboard

---

## Archivos por workstream

| Workstream | Archivos |
|---|---|
| A2 | `page.tsx` (modify), `_components/product-grid-card.tsx` (create), `components/domain/product-edit-drawer.tsx` (modify) |
| B2 | `[sku]/_components/product-tabs-connected.tsx` (create), `[sku]/layout.tsx` (modify), `[sku]/_components/product-header.tsx` (modify) |
| C2 | `_components/saved-views-bar.tsx` (modify), `lib/hooks/use-saved-views.ts` (modify) |

---

# WORKSTREAM A2 — Vista Galería + Quick Edit + Estado Vacío Inteligente + Nav Context

**Archivos base:**
- `mt-pricing-frontend/app/(app)/catalogo/page.tsx`
- `mt-pricing-frontend/app/(app)/catalogo/_components/product-grid-card.tsx` (nuevo)
- `mt-pricing-frontend/components/domain/product-edit-drawer.tsx`

---

### Task A2-1: Crear `ProductGridCard`

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/_components/product-grid-card.tsx`

- [ ] **Step 1: Crear el archivo con el componente completo**

```tsx
"use client";

import Link from "next/link";
import { Pencil } from "lucide-react";
import { MT } from "@/components/mt/tokens";
import { QualityBadge, Thumb } from "@/components/mt/primitives";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import type { ProductListItem } from "@/lib/api/endpoints/products";
import { getProductName } from "@/lib/utils/product-display";

interface ProductGridCardProps {
  item: ProductListItem;
  onQuickEdit: (sku: string) => void;
  onNavClick: () => void;
}

export function ProductGridCard({ item, onQuickEdit, onNavClick }: ProductGridCardProps) {
  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-lg border transition-shadow hover:shadow-md"
      style={{ borderColor: MT.border, background: MT.surface }}
    >
      {/* Imagen — link al detalle */}
      <Link
        href={`/catalogo/${item.sku}`}
        onClick={onNavClick}
        className="block"
      >
        <div
          className="flex h-[120px] items-center justify-center overflow-hidden"
          style={{ background: MT.surface2 }}
        >
          {item.primary_image_url ? (
            <img
              src={item.primary_image_url}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            <Thumb />
          )}
        </div>
      </Link>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <span
          className="mt-mono text-[10px] uppercase tracking-wider"
          style={{ color: MT.brand }}
        >
          {item.sku}
        </span>
        <Link
          href={`/catalogo/${item.sku}`}
          onClick={onNavClick}
          className="line-clamp-2 text-[12px] font-medium leading-tight hover:underline"
          style={{ color: MT.ink }}
        >
          {getProductName(item)}
        </Link>
        {item.family ? (
          <span
            className="mt-mono truncate text-[10.5px]"
            style={{ color: MT.ink4 }}
          >
            {item.family}
          </span>
        ) : null}

        {/* Footer: badges + acción */}
        <div className="mt-auto flex items-center justify-between pt-1">
          <div className="flex items-center gap-1">
            <QualityBadge v={item.data_quality} />
            <LifecycleStatusBadge status={item.lifecycle_status} />
          </div>
          <button
            type="button"
            onClick={() => onQuickEdit(item.sku)}
            className="rounded p-1 opacity-0 transition-opacity group-hover:opacity-100"
            style={{ color: MT.ink3 }}
            title="Editar rápido"
          >
            <Pencil className="size-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verificar que `LifecycleStatusBadge` existe en el path correcto**

```powershell
Test-Path "mt-pricing-frontend/components/ui/lifecycle-status-badge.tsx"
```

Si no existe, reemplaza `<LifecycleStatusBadge status={item.lifecycle_status} />` con `null` en el componente y elimina el import.

- [ ] **Step 3: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "product-grid-card"
```

Expected: sin errores para este archivo.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/_components/product-grid-card.tsx
git commit -m "feat(catalog): add ProductGridCard for gallery view"
```

---

### Task A2-2: Hacer `product` opcional en `ProductEditDrawer`

**Files:**
- Modify: `mt-pricing-frontend/components/domain/product-edit-drawer.tsx`

Actualmente `product: Product` es un prop requerido. Necesitamos hacerlo opcional para poder abrir el drawer desde la tabla (donde solo tenemos el SKU). Cuando `product` no se pasa, el drawer lo fetcha internamente usando `useProduct(sku)`.

- [ ] **Step 1: Agregar import de `useProduct`** al bloque de imports existente

```tsx
// Añadir debajo de: import { productKeys } from "@/lib/hooks/products/query-keys";
import { useProduct } from "@/lib/hooks/products/use-product";
```

- [ ] **Step 2: Cambiar la interfaz `Props`** — hacer `product` opcional

Reemplazar:
```tsx
interface Props {
  sku: string;
  product: Product;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
```

Por:
```tsx
interface Props {
  sku: string;
  /** Pasar cuando el producto ya está en caché (p.ej. desde el header del detalle).
   *  Si se omite, el drawer lo fetcha internamente por SKU. */
  product?: Product;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
```

- [ ] **Step 3: Actualizar la firma de la función** y agregar fetch interno

Reemplazar la línea:
```tsx
export function ProductEditDrawer({ sku, product, open, onOpenChange }: Props) {
```

Por:
```tsx
export function ProductEditDrawer({ sku, product: productProp, open, onOpenChange }: Props) {
  const { data: fetchedProduct, isLoading: isProductLoading } = useProduct(sku);
  const product = productProp ?? fetchedProduct;
```

- [ ] **Step 4: Cambiar el `useState` inicial de `draft`** para no usar `product` en la inicialización (ya que puede ser undefined al inicio)

Reemplazar:
```tsx
const [draft, setDraft] = React.useState({
  name_es: (product.translations?.es?.name ?? "") as string,
  name_ar: (product.translations?.ar?.name ?? "") as string,
  brand: product.brand ?? "",
  gtin: product.gtin ?? "",
  lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
  data_quality: (product.data_quality ?? "partial") as DataQuality,
});
```

Por:
```tsx
const [draft, setDraft] = React.useState({
  name_es: "" as string,
  name_ar: "" as string,
  brand: "",
  gtin: "",
  lifecycle_status: "active" as ProductLifecycleStatus,
  data_quality: "partial" as DataQuality,
});
```

- [ ] **Step 5: Actualizar el `useEffect` de sincronización** para que sea null-safe

Reemplazar:
```tsx
React.useEffect(() => {
  setDraft({
    name_es: (product.translations?.es?.name ?? "") as string,
    name_ar: (product.translations?.ar?.name ?? "") as string,
    brand: product.brand ?? "",
    gtin: product.gtin ?? "",
    lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
    data_quality: (product.data_quality ?? "partial") as DataQuality,
  });
}, [product]);
```

Por:
```tsx
React.useEffect(() => {
  if (!product) return;
  setDraft({
    name_es: (product.translations?.es?.name ?? "") as string,
    name_ar: (product.translations?.ar?.name ?? "") as string,
    brand: product.brand ?? "",
    gtin: product.gtin ?? "",
    lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
    data_quality: (product.data_quality ?? "partial") as DataQuality,
  });
}, [product]);
```

- [ ] **Step 6: Actualizar `handleSave`** para que sea null-safe

Agregar guard al inicio de `handleSave`:
```tsx
const handleSave = () => {
  if (!product) return;
  const original = product;
  // ... resto igual
```

- [ ] **Step 7: Envolver el contenido del Sheet con estado de carga**

Reemplazar el contenido del `<Sheet>` (todo dentro de `<SheetContent>`):
```tsx
<Sheet open={open} onOpenChange={onOpenChange}>
  <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
    {!product && isProductLoading ? (
      <div className="flex h-40 items-center justify-center">
        <span className="text-sm text-muted-foreground">Cargando…</span>
      </div>
    ) : product ? (
      <>
        <SheetHeader className="mb-6">
          <SheetTitle className="font-mono text-sm text-muted-foreground">
            Editar {sku}
          </SheetTitle>
        </SheetHeader>

        <div className="space-y-5">
          {/* Nombre ES */}
          <div className="space-y-1.5">
            <Label htmlFor="name_es">Nombre (ES)</Label>
            <Input
              id="name_es"
              value={draft.name_es}
              onChange={(e) =>
                setDraft((d) => ({ ...d, name_es: e.target.value }))
              }
              placeholder="Nombre en español"
            />
          </div>

          {/* Nombre AR */}
          <div className="space-y-1.5">
            <Label htmlFor="name_ar">Nombre (AR)</Label>
            <Input
              id="name_ar"
              value={draft.name_ar}
              onChange={(e) =>
                setDraft((d) => ({ ...d, name_ar: e.target.value }))
              }
              placeholder="Nombre en árabe"
              dir="rtl"
            />
          </div>

          {/* Marca */}
          <div className="space-y-1.5">
            <Label htmlFor="brand">Marca</Label>
            <Input
              id="brand"
              value={draft.brand}
              onChange={(e) =>
                setDraft((d) => ({ ...d, brand: e.target.value }))
              }
              placeholder="—"
            />
          </div>

          {/* GTIN */}
          <div className="space-y-1.5">
            <Label htmlFor="gtin">GTIN</Label>
            <Input
              id="gtin"
              value={draft.gtin}
              onChange={(e) =>
                setDraft((d) => ({ ...d, gtin: e.target.value }))
              }
              placeholder="—"
              maxLength={14}
              className="font-mono"
            />
          </div>

          {/* Lifecycle Status */}
          <div className="space-y-1.5">
            <Label>Estado lifecycle</Label>
            <Select
              value={draft.lifecycle_status}
              onValueChange={(v) =>
                setDraft((d) => ({
                  ...d,
                  lifecycle_status: v as ProductLifecycleStatus,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LIFECYCLE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Data Quality */}
          <div className="space-y-1.5">
            <Label>Calidad de datos</Label>
            <Select
              value={draft.data_quality}
              onValueChange={(v) =>
                setDraft((d) => ({
                  ...d,
                  data_quality: v as DataQuality,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {QUALITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Acceso a formulario completo */}
          <div className="border-t pt-4">
            <a
              href={`/catalogo/${sku}/edit`}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Editar todos los campos técnicos →
            </a>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={patchMutation.isPending}
          >
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={patchMutation.isPending}>
            {patchMutation.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </div>
      </>
    ) : null}
  </SheetContent>
</Sheet>
```

- [ ] **Step 8: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "product-edit-drawer"
```

Expected: sin errores.

- [ ] **Step 9: Verificar que product-header.tsx sigue compilando** (pasaba `product` como required, ahora es optional pero retrocompatible)

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "product-header"
```

Expected: sin errores.

- [ ] **Step 10: Commit**

```bash
git add mt-pricing-frontend/components/domain/product-edit-drawer.tsx
git commit -m "feat(catalog): make product prop optional in ProductEditDrawer (fetches by SKU internally)"
```

---

### Task A2-3: Vista Galería toggle + Quick Edit + Nav Context en `page.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

Esta task modifica `page.tsx` en múltiples puntos. Lee el archivo completo antes de editar.

- [ ] **Step 1: Agregar imports faltantes** al bloque de imports de lucide-react

Localizar la línea de lucide imports (actualmente `Copy, Download, Image as ImageIcon, MoreHorizontal, Pencil, Plus, Upload, X`) y agregar `LayoutGrid, List`:

```tsx
import {
  Copy,
  Download,
  Image as ImageIcon,
  LayoutGrid,
  List,
  MoreHorizontal,
  Pencil,
  Plus,
  Upload,
  X,
} from "lucide-react";
```

- [ ] **Step 2: Agregar import de `ProductEditDrawer`** y `ProductGridCard` al bloque de imports locales (justo antes o después de los otros imports de `_components`):

```tsx
import { ProductEditDrawer } from "@/components/domain/product-edit-drawer";
import { ProductGridCard } from "./_components/product-grid-card";
```

- [ ] **Step 3: Agregar función `storeNavContext`** — justo debajo de la función `fmtUpdated` (antes del componente `CatalogPage`):

```tsx
function storeNavContext(skus: string[]): void {
  try {
    sessionStorage.setItem("mt-catalog-nav", JSON.stringify(skus));
  } catch {
    // ignore — sessionStorage unavailable (SSR, private mode)
  }
}
```

- [ ] **Step 4: Agregar estado `viewMode` y `quickEditSku`** al componente `CatalogPage`, después del bloque de estados existentes (después de `pageLimit`):

```tsx
// A2 — modo de visualización
const [viewMode, setViewMode] = React.useState<"table" | "grid">("table");
// A2 — quick edit desde tabla/galería
const [quickEditSku, setQuickEditSku] = React.useState<string | null>(null);
```

- [ ] **Step 5: Agregar el toggle de vista al toolbar**

Localizar la sección del toolbar con los botones de acción (la `<div className="flex gap-1.5">` que contiene MtButton Importer/Exportar/Alta SKU). Agregar el toggle ANTES de esos botones:

Reemplazar:
```tsx
<div className="flex gap-1.5">
  <MtButton asChild>
    <Link href="/imports">
```

Por:
```tsx
<div className="flex items-center gap-1.5">
  {/* A2 — vista toggle */}
  <div
    className="flex items-center gap-0.5 rounded-md border p-0.5"
    style={{ borderColor: MT.border }}
  >
    <button
      type="button"
      title="Vista tabla"
      onClick={() => setViewMode("table")}
      className="rounded p-1 transition-colors"
      style={{
        background: viewMode === "table" ? MT.brand : "transparent",
        color: viewMode === "table" ? "white" : MT.ink3,
      }}
    >
      <List className="size-3.5" />
    </button>
    <button
      type="button"
      title="Vista galería"
      onClick={() => setViewMode("grid")}
      className="rounded p-1 transition-colors"
      style={{
        background: viewMode === "grid" ? MT.brand : "transparent",
        color: viewMode === "grid" ? "white" : MT.ink3,
      }}
    >
      <LayoutGrid className="size-3.5" />
    </button>
  </div>
  <MtButton asChild>
    <Link href="/imports">
```

- [ ] **Step 6: Agregar onClick de nav context al link del Nombre en la fila de tabla**

Localizar el `<Link href={`/catalogo/${r.sku}`} className="line-clamp-1 hover:underline">` dentro del tbody (la celda Nombre). Agregar `onClick`:

```tsx
<Link
  href={`/catalogo/${r.sku}`}
  className="line-clamp-1 hover:underline"
  onClick={() => storeNavContext(items.map((i) => i.sku))}
>
  {getProductName(r)}
</Link>
```

- [ ] **Step 7: Agregar onClick de nav context al link del SKU** en la celda SKU:

```tsx
<MtTd mono className="font-medium" style={{ color: MT.brand }}>
  <Link
    href={`/catalogo/${r.sku}`}
    onClick={() => storeNavContext(items.map((i) => i.sku))}
  >
    {r.sku}
  </Link>
</MtTd>
```

- [ ] **Step 8: Reemplazar el botón "Editar" en hover actions** para que abra el quick edit drawer en lugar de navegar a `/edit`

Localizar la celda `{/* Acciones — A-4 */}` y reemplazar el `<Link href=".../edit">` por un botón que setea `quickEditSku`:

Reemplazar:
```tsx
<Link
  href={`/catalogo/${r.sku}/edit`}
  onClick={(e) => e.stopPropagation()}
  className="inline-flex h-6 items-center gap-1 rounded px-2 text-[11px] font-medium transition-colors hover:bg-mt-surface-2"
  style={{ color: MT.brand }}
  title="Editar"
>
  <Pencil className="size-3" />
  Editar
</Link>
```

Por:
```tsx
<button
  type="button"
  onClick={(e) => {
    e.stopPropagation();
    setQuickEditSku(r.sku);
  }}
  className="inline-flex h-6 items-center gap-1 rounded px-2 text-[11px] font-medium transition-colors hover:bg-mt-surface-2"
  style={{ color: MT.brand }}
  title="Editar rápido"
>
  <Pencil className="size-3" />
  Editar
</button>
```

- [ ] **Step 9: Agregar onClick de nav context al `<Link>` de MoreHorizontal** (el icono que aparece cuando no hay hover):

```tsx
<Link
  href={`/catalogo/${r.sku}`}
  aria-label={`Ver ${r.sku}`}
  onClick={() => storeNavContext(items.map((i) => i.sku))}
>
  <MoreHorizontal
    className="size-3.5 cursor-pointer"
    style={{ color: MT.ink4 }}
  />
</Link>
```

- [ ] **Step 10: Reemplazar el estado vacío** (el `<MtEmpty>` al final del `<div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">`) por estado vacío inteligente con sugerencias de filtros:

Reemplazar:
```tsx
{!isLoading && items.length === 0 && !isError ? (
  <MtEmpty
    title="Sin resultados"
    hint="Ajusta los filtros o limpia la búsqueda."
    icon={<ImageIcon className="size-6" strokeWidth={1.4} />}
  />
) : null}
```

Por:
```tsx
{!isLoading && items.length === 0 && !isError ? (
  <div className="flex flex-col items-center gap-4 px-6 py-16">
    <ImageIcon
      className="size-9 opacity-20"
      style={{ color: MT.ink3 }}
      strokeWidth={1.2}
    />
    <div className="text-center">
      <p className="text-[13px] font-medium" style={{ color: MT.ink }}>
        Sin resultados
      </p>
      <p className="mt-0.5 text-[12px]" style={{ color: MT.ink3 }}>
        No hay productos con los filtros actuales.
      </p>
    </div>
    {activeChips.length > 0 ? (
      <div className="flex flex-col items-center gap-2">
        <p className="text-[11px]" style={{ color: MT.ink4 }}>
          Prueba quitando algún filtro:
        </p>
        <div className="flex flex-wrap justify-center gap-1.5">
          {activeChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => removeChip(chip.key)}
              className="rounded-full border px-2.5 py-0.5 text-[11px] transition-colors hover:border-current"
              style={{ borderColor: MT.border, color: MT.ink3 }}
            >
              Quitar «{chip.label}» ×
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={clearAllFilters}
          className="mt-1 text-[11px] font-medium underline-offset-2 hover:underline"
          style={{ color: MT.brand }}
        >
          Limpiar todos los filtros
        </button>
      </div>
    ) : null}
  </div>
) : null}
```

- [ ] **Step 11: Agregar la Vista Galería** — wrapper condicional alrededor del `<div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">` existente

Localizar la línea `{/* Table */}` (o `<div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">`). El objetivo es que, cuando `viewMode === "grid"`, se muestre la grilla en lugar de la tabla. Agregar el bloque de galería ANTES de la tabla existente:

Reemplazar (solo el div de tabla, manteniendo lo que hay dentro):
```tsx
{/* Table */}
<div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">
```

Por:
```tsx
{/* A2 — Vista Galería */}
{viewMode === "grid" ? (
  <div
    className="mt-thin-scroll grid flex-1 grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3 overflow-auto p-4"
    style={{ background: MT.surface }}
  >
    {isLoading
      ? Array.from({ length: 12 }).map((_, idx) => (
          <div
            key={`sk-${idx}`}
            className="h-[220px] animate-pulse rounded-lg"
            style={{ background: MT.surface2, border: `1px solid ${MT.border}` }}
          />
        ))
      : null}
    {!isLoading
      ? items.map((r) => (
          <ProductGridCard
            key={r.sku}
            item={r}
            onQuickEdit={(sku) => setQuickEditSku(sku)}
            onNavClick={() => storeNavContext(items.map((i) => i.sku))}
          />
        ))
      : null}
    {!isLoading && items.length === 0 && !isError ? (
      <div
        className="col-span-full flex flex-col items-center gap-3 py-12"
        style={{ color: MT.ink3 }}
      >
        <ImageIcon className="size-8 opacity-20" strokeWidth={1.2} />
        <p className="text-[13px]">Sin resultados</p>
        {activeChips.length > 0 ? (
          <button
            type="button"
            onClick={clearAllFilters}
            className="text-[11.5px] font-medium"
            style={{ color: MT.brand }}
          >
            Limpiar filtros
          </button>
        ) : null}
      </div>
    ) : null}
  </div>
) : null}

{/* Table */}
{viewMode === "table" ? (
<div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">
```

Y al final del div de tabla (después del estado vacío inteligente pero antes del `</div>` de cierre), agregar:
```tsx
</div>
) : null}
```

**Nota:** Asegúrate de que el div de galería y el de tabla sean ambos `flex-1` para llenar el espacio correctamente.

- [ ] **Step 12: Montar el `ProductEditDrawer` de quick edit** al final del JSX del componente (justo antes del cierre del `</div>` principal del componente, después del `<Paginator>`):

```tsx
{/* A2 — Quick Edit Drawer desde tabla/galería */}
{quickEditSku !== null ? (
  <ProductEditDrawer
    sku={quickEditSku}
    open={true}
    onOpenChange={(o) => {
      if (!o) setQuickEditSku(null);
    }}
  />
) : null}
```

- [ ] **Step 13: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "catalogo/page"
```

Expected: sin errores.

- [ ] **Step 14: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/page.tsx
git commit -m "feat(catalog): gallery view toggle, quick edit drawer, nav context, smart empty state"
```

---

### Task A2-4: Redesplegar y verificar

- [ ] **Step 1: Redesplegar el frontend**

```powershell
docker restart mt-frontend
```

- [ ] **Step 2: Verificar que el toggle de vista funciona**

Abrir `http://localhost:8080/catalogo`. Verificar:
- Los dos botones de toggle (lista/galería) aparecen en el toolbar
- Al hacer click en galería, se muestra la vista de cards
- Al hacer click en tabla, vuelve la tabla normal
- En galería, hover sobre card muestra el botón de editar con ícono de lápiz
- Click en editar abre el drawer de edición
- En tabla, hover muestra botón "Editar" que abre drawer (no navega a /edit)
- Vaciar todos los resultados con filtros agresivos → se muestran sugerencias de filtros a quitar
- Click en un nombre o SKU navega al detalle

- [ ] **Step 3: Verificar sessionStorage**

En DevTools > Application > Session Storage:
- Después de hacer click en un producto, debe existir la clave `mt-catalog-nav` con un array de SKUs

---

# WORKSTREAM B2 — Detalle Prev/Next + hasImage badge dinámico

**Archivos base:**
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs-connected.tsx` (nuevo)
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx`
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`

---

### Task B2-1: Crear `ProductTabsConnected`

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs-connected.tsx`

El objetivo es que el badge ⚠ en el tab "Imágenes" se active dinámicamente cuando el producto no tiene imagen. El `layout.tsx` es un Server Component, por lo que no puede usar TanStack Query. Creamos un thin client wrapper que usa `useProduct(sku)` (comparte caché con `ProductHeader`) y pasa `hasImage` al `ProductTabs`.

- [ ] **Step 1: Crear el archivo**

```tsx
"use client";

import { useProduct } from "@/lib/hooks/products/use-product";
import { ProductTabs } from "./product-tabs";

interface Props {
  sku: string;
}

export function ProductTabsConnected({ sku }: Props) {
  const { data: product } = useProduct(sku);
  return (
    <ProductTabs
      sku={sku}
      hasImage={product ? !!product.primary_image_url : true}
    />
  );
}
```

**Nota sobre `hasImage={true}` como fallback:** Mientras el producto carga, mostramos `true` para evitar parpadeo de la alerta ⚠. Una vez que `product` resuelve, si `primary_image_url` es null, el badge aparece automáticamente.

- [ ] **Step 2: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "product-tabs-connected"
```

Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs-connected.tsx"
git commit -m "feat(catalog): ProductTabsConnected — dynamic hasImage badge via TanStack Query cache"
```

---

### Task B2-2: Actualizar `layout.tsx` para usar `ProductTabsConnected`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx`

- [ ] **Step 1: Leer el archivo actual** (verificar las líneas exactas antes de editar)

```powershell
Get-Content "mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx"
```

El archivo actual importa `ProductTabs` y lo usa como `<ProductTabs sku={sku} />`.

- [ ] **Step 2: Agregar import de `ProductTabsConnected`**

Agregar junto al import de `ProductTabs`:
```tsx
import { ProductTabsConnected } from "./_components/product-tabs-connected";
```

- [ ] **Step 3: Reemplazar `<ProductTabs sku={sku} />`** por `<ProductTabsConnected sku={sku} />`

```tsx
{/* Antes: */}
<ProductTabs sku={sku} />

{/* Después: */}
<ProductTabsConnected sku={sku} />
```

Nota: Puedes mantener el import de `ProductTabs` si lo usas en otro lugar, o eliminarlo si solo era para este uso.

- [ ] **Step 4: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "catalogo/\[sku\]/layout"
```

Expected: sin errores.

- [ ] **Step 5: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx"
git commit -m "feat(catalog): use ProductTabsConnected in detail layout for dynamic hasImage badge"
```

---

### Task B2-3: Agregar navegación Prev/Next al `ProductHeader`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`

Añadimos una barra de navegación compacta encima del header del detalle. Lee el sessionStorage `mt-catalog-nav` (guardado cuando el usuario hace click desde el catálogo) y muestra botones ‹ Anterior / Siguiente › con contador de posición.

- [ ] **Step 1: Agregar imports necesarios**

En la línea de imports de lucide-react (actualmente `Barcode, ImageIcon, Layers, GitBranch, Pencil, Ruler`), agregar `ChevronLeft, ChevronRight`:

```tsx
import { Barcode, ChevronLeft, ChevronRight, ImageIcon, Layers, GitBranch, Pencil, Ruler } from "lucide-react";
```

Verificar que `React` está disponible (el archivo usa `useState`, así que React está importado). Si no, también hay que importar `useEffect`.

- [ ] **Step 2: Agregar `useState` para `navSkus`** en el cuerpo del componente `ProductHeader`, después de la declaración de `drawerOpen`:

```tsx
const [drawerOpen, setDrawerOpen] = React.useState(false); // ya existe

// B2 — prev/next nav desde el catálogo
const [navSkus, setNavSkus] = React.useState<string[]>([]);
React.useEffect(() => {
  try {
    const raw = sessionStorage.getItem("mt-catalog-nav");
    if (raw) setNavSkus(JSON.parse(raw) as string[]);
  } catch {
    // ignore
  }
}, []);
```

**Nota:** `useState` e `useEffect` actualmente se importan de React con `import { useState } from "react"`. Cambiar a `import React, { useState } from "react"` o agregar `useEffect` al named import:
```tsx
import { useState, useEffect } from "react";
```
Y luego usar `useEffect` en lugar de `React.useEffect` — o directamente usar la sintaxis que el archivo ya use.

- [ ] **Step 3: Calcular prev/next** después del bloque `useEffect`:

```tsx
const navIdx = navSkus.indexOf(sku);
const prevSku = navIdx > 0 ? navSkus[navIdx - 1] : null;
const nextSku = navIdx > 0 || navSkus.length > 0
  ? navIdx < navSkus.length - 1 ? navSkus[navIdx + 1] : null
  : null;
const showNav = navSkus.length > 0 && navIdx >= 0;
```

- [ ] **Step 4: Agregar la barra de navegación al JSX** — justo después del `<ProductEditDrawer ... />` y ANTES del `<div className="flex gap-5">` del layout principal:

```tsx
{/* B2 — Prev/Next navigation bar */}
{showNav ? (
  <div className="mb-2 flex items-center gap-3 text-[11.5px]" style={{ color: "hsl(var(--muted-foreground))" }}>
    <Link
      href="/catalogo"
      className="hover:text-foreground transition-colors"
    >
      ← Catálogo
    </Link>
    <span className="text-muted-foreground/30">|</span>
    {prevSku ? (
      <Link
        href={`/catalogo/${prevSku}`}
        className="flex items-center gap-0.5 font-mono hover:text-foreground transition-colors"
      >
        <ChevronLeft className="size-3.5" />
        {prevSku}
      </Link>
    ) : (
      <span className="flex items-center gap-0.5 opacity-30">
        <ChevronLeft className="size-3.5" />
        —
      </span>
    )}
    <span className="tabular-nums">
      {navIdx + 1} / {navSkus.length}
    </span>
    {nextSku ? (
      <Link
        href={`/catalogo/${nextSku}`}
        className="flex items-center gap-0.5 font-mono hover:text-foreground transition-colors"
      >
        {nextSku}
        <ChevronRight className="size-3.5" />
      </Link>
    ) : (
      <span className="flex items-center gap-0.5 opacity-30">
        —
        <ChevronRight className="size-3.5" />
      </span>
    )}
  </div>
) : null}
```

- [ ] **Step 5: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "product-header"
```

Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx"
git commit -m "feat(catalog): prev/next navigation bar in product detail header (reads sessionStorage)"
```

---

### Task B2-4: Redesplegar y verificar

- [ ] **Step 1: Redesplegar el frontend**

```powershell
docker restart mt-frontend
```

- [ ] **Step 2: Verificar hasImage badge**

Abrir un producto SIN imagen principal en `/catalogo/[sku]`. El tab "Imágenes" debe mostrar el badge ⚠ en color ámbar.

Abrir un producto CON imagen principal. El badge ⚠ no debe aparecer en "Imágenes".

- [ ] **Step 3: Verificar navegación prev/next**

1. Ir a `/catalogo` y hacer click en un producto de la lista (en el nombre o SKU)
2. En el detalle, debe aparecer la barra "← Catálogo | ‹ SKU_ANTERIOR | N/Total | SKU_SIGUIENTE ›"
3. Hacer click en el siguiente → navega al siguiente SKU y la barra actualiza el contador
4. Abrir `/catalogo/[sku]` directamente sin pasar por el catálogo → la barra no aparece (sessionStorage vacío)

---

# WORKSTREAM C2 — Vistas Guardadas: "Revisión de calidad" + URLs Compartibles

**Archivos base:**
- `mt-pricing-frontend/app/(app)/catalogo/_components/saved-views-bar.tsx`
- `mt-pricing-frontend/lib/hooks/use-saved-views.ts`
- `mt-pricing-frontend/app/(app)/catalogo/page.tsx` (pequeño cambio: pasar `onShareView`)

---

### Task C2-1: Agregar `getShareUrl` al hook de vistas guardadas

**Files:**
- Modify: `mt-pricing-frontend/lib/hooks/use-saved-views.ts`

- [ ] **Step 1: Leer el archivo actual**

```powershell
Get-Content "mt-pricing-frontend/lib/hooks/use-saved-views.ts"
```

El archivo exporta `useSavedViews()` con `views`, `addView`, `removeView`.

- [ ] **Step 2: Agregar la función exportada `getShareUrl`** al final del archivo, antes del export del hook:

```tsx
/**
 * Serializa los filtros de una vista como URL params de la página de catálogo.
 * Los nombres de params deben coincidir con los useQueryState de page.tsx.
 */
export function getShareUrl(filters: Partial<import("@/lib/api/endpoints/facets").FacetsFilters>): string {
  const params = new URLSearchParams();
  if (filters.family) params.set("family", filters.family);
  if (filters.material) params.set("material", filters.material);
  if (filters.dn) params.set("dn", filters.dn);
  if (filters.pn) params.set("pn", filters.pn);
  if (filters.data_quality) params.set("quality", filters.data_quality as string);
  if (filters.translation_status) params.set("translation", filters.translation_status as string);
  if (filters.active != null) params.set("active", String(filters.active));
  if (filters.division) params.set("division", filters.division);
  if (filters.series_id) params.set("series_id", filters.series_id);
  if (filters.material_id) params.set("material_id", filters.material_id);
  if (filters.tier_code) params.set("tier_code", filters.tier_code);
  const q = params.toString();
  return `/catalogo${q ? `?${q}` : ""}`;
}
```

**Nota:** Los nombres de los params (`quality`, `translation`, `active`, etc.) deben coincidir exactamente con los `useQueryState` de `page.tsx`. Verificar si hay discrepancias comparando con el archivo `page.tsx` si es necesario.

- [ ] **Step 3: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "use-saved-views"
```

Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/lib/hooks/use-saved-views.ts
git commit -m "feat(catalog): add getShareUrl helper to serialize view filters as URL params"
```

---

### Task C2-2: Actualizar `SavedViewsBar` — "Revisión de calidad" + botón copy link

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/_components/saved-views-bar.tsx`

- [ ] **Step 1: Agregar import de `Link2` de lucide** al archivo

Al principio del archivo, `saved-views-bar.tsx` no importa desde lucide. Agregar:
```tsx
import { Link2 } from "lucide-react";
```

- [ ] **Step 2: Agregar prop `onShareView` a la interfaz `SavedViewsBarProps`**

En la interfaz, agregar:
```tsx
/** Compartir URL de una vista de usuario por id. */
onShareView?: (id: string) => void;
```

- [ ] **Step 3: Agregar `onShareView` a la desestructuración del componente**

```tsx
export function SavedViewsBar({
  views,
  activeId,
  onSelect,
  userViews = [],
  onSaveCurrentView,
  onDeleteView,
  onShareView,      // ← agregar
}: SavedViewsBarProps) {
```

- [ ] **Step 4: Agregar la vista de sistema "Revisión de calidad"** al array `SYSTEM_VIEWS` exportado al final del archivo

Localizar:
```tsx
export const SYSTEM_VIEWS: SavedView[] = [
  { id: "all", name: "Todos", filters: {} },
  ...
  { id: "div-industrial", name: "Industrial", filters: { division: "industrial" } },
];
```

Agregar al final del array (antes del corchete de cierre):
```tsx
{ id: "quality-review", name: "Revisar calidad", filters: { data_quality: "partial" } },
```

**Nota sobre tipo:** `data_quality: "partial"` debe ser compatible con `Partial<FacetsFilters>`. Si `FacetsFilters` define `data_quality` con un tipo diferente (como una unión), puede necesitar un cast: `data_quality: "partial" as import("@/lib/api/endpoints/products").DataQuality`. Verificar después del TypeScript check.

- [ ] **Step 5: Modificar el renderizado de las vistas de usuario** para mostrar botones × y share en hover, sin el padding-right hack actual

Localizar el bloque de vistas de usuario (la sección `{userViews.map((uv) => { ... })}`) y reemplazarlo completo con:

```tsx
{/* Vistas guardadas por el usuario */}
{userViews.map((uv) => {
  const active = uv.id === activeId;
  return (
    <span key={uv.id} className="group flex shrink-0 items-center gap-0.5">
      <button
        type="button"
        onClick={() => onSelect(uv)}
        className="flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] transition-colors"
        style={{
          background: active ? MT.brand : "transparent",
          color: active ? "white" : MT.ink3,
          border: `1px solid ${active ? MT.brand : MT.border}`,
        }}
        title={`Vista guardada: ${uv.name}`}
      >
        <span
          className="size-1.5 rounded-full"
          style={{ background: active ? "rgba(255,255,255,0.7)" : MT.ink4 }}
        />
        <span>{uv.name}</span>
      </button>

      {/* Acciones en hover — share + delete */}
      <span className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        {onShareView ? (
          <button
            type="button"
            aria-label={`Copiar enlace de "${uv.name}"`}
            title="Copiar enlace"
            onClick={(e) => {
              e.stopPropagation();
              onShareView(uv.id);
            }}
            className="rounded-full p-0.5"
            style={{ color: active ? MT.brand : MT.ink4 }}
          >
            <Link2 className="size-3" />
          </button>
        ) : null}
        {onDeleteView ? (
          <button
            type="button"
            aria-label={`Eliminar vista "${uv.name}"`}
            onClick={(e) => {
              e.stopPropagation();
              onDeleteView(uv.id);
            }}
            className="rounded-full p-0.5"
            style={{ color: active ? MT.brand : MT.ink4 }}
          >
            <svg
              width="10"
              height="10"
              viewBox="0 0 10 10"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
            >
              <line x1="2" y1="2" x2="8" y2="8" />
              <line x1="8" y1="2" x2="2" y2="8" />
            </svg>
          </button>
        ) : null}
      </span>
    </span>
  );
})}
```

- [ ] **Step 6: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "saved-views-bar"
```

Expected: sin errores. Si hay error con `data_quality: "partial"`, agregar cast explícito.

- [ ] **Step 7: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/_components/saved-views-bar.tsx
git commit -m "feat(catalog): add quality-review system view + share URL button on user views"
```

---

### Task C2-3: Conectar `onShareView` desde `page.tsx`

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Agregar import de `getShareUrl`** al bloque de imports de hooks:

```tsx
import { useSavedViews, getShareUrl } from "@/lib/hooks/use-saved-views";
```

- [ ] **Step 2: Agregar el callback `handleShareView`** en el cuerpo del componente `CatalogPage`, junto a los otros callbacks de vistas:

```tsx
const handleShareView = React.useCallback(
  (id: string) => {
    const view = savedUserViews.find((v) => v.id === id);
    if (!view) return;
    const url = `${window.location.origin}${getShareUrl(view.filters)}`;
    void navigator.clipboard
      .writeText(url)
      .then(() => toast.success("URL copiada al portapapeles"))
      .catch(() => toast.error("No se pudo copiar la URL"));
  },
  [savedUserViews],
);
```

- [ ] **Step 3: Pasar `onShareView` al `<SavedViewsBar>`**

Localizar el `<SavedViewsBar ... />` en el JSX y agregar la prop:

```tsx
<SavedViewsBar
  views={SYSTEM_VIEWS.map((v) => ({
    ...v,
    count: ...
  }))}
  activeId={activeViewId}
  onSelect={handleSelectView}
  userViews={savedUserViews}
  onSaveCurrentView={handleSaveCurrentView}
  onDeleteView={removeView}
  onShareView={handleShareView}   {/* ← agregar */}
/>
```

- [ ] **Step 4: Verificar que la vista "Revisión de calidad" funciona correctamente**

Verificar que `activeViewId` detecta correctamente la vista "Revisión de calidad". Localizar la función `activeViewId` useMemo (alrededor de línea 495-503 del archivo actual) y verificar que reconoce `data_quality === "partial"`:

```tsx
const activeViewId = React.useMemo(() => {
  const otherFilters = [family, material, dn, pn, quality, translationStatus].filter(Boolean).length;
  if (otherFilters === 0 && active === true) return "active-only";
  if (family === "unclassified" && otherFilters === 1 && active === null) return "unclassified";
  if (translationStatus === "pending" && otherFilters === 1 && active === null) return "pending-es";
  if (quality === "partial" && otherFilters === 1 && active === null) return "quality-review"; // ← agregar
  if (otherFilters === 0 && (active === null || active === undefined)) return "all";
  return "";
}, [active, family, material, dn, pn, quality, translationStatus]);
```

- [ ] **Step 5: Verificar TypeScript**

```powershell
cd mt-pricing-frontend; npx tsc --noEmit --project tsconfig.json 2>&1 | Select-String "catalogo/page"
```

Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add mt-pricing-frontend/app/\(app\)/catalogo/page.tsx
git commit -m "feat(catalog): wire onShareView + quality-review view detection in CatalogPage"
```

---

### Task C2-4: Redesplegar y verificar

- [ ] **Step 1: Redesplegar el frontend**

```powershell
docker restart mt-frontend
```

- [ ] **Step 2: Verificar "Revisión de calidad"**

Abrir `/catalogo`. En la barra de vistas guardadas debe aparecer "Revisar calidad". Click en ella debe activar el filtro `quality=partial` en la URL y mostrar solo productos con calidad parcial.

- [ ] **Step 3: Verificar URL compartible**

Guardar una vista de usuario con algunos filtros activos. En hover de la vista guardada, debe aparecer el ícono de enlace. Click en él → debe copiarse una URL al portapapeles (verificar con toast "URL copiada al portapapeles").

Abrir la URL copiada en una pestaña nueva → debe cargar el catálogo con los filtros aplicados.

---

## Notas de Fase 3 (futuro)

- **Taxonomía visual avanzada**: tree-nav lateral, drill-down por familia/serie/material sin búsqueda
- **Modo comparación**: seleccionar 2-4 SKUs y ver specs side-by-side
- **Vista "tour de calidad"**: navegar secuencialmente solo por productos con `data_quality="partial"` (combinar savedView + sessionStorage nav)
- **Filtros persistentes**: recordar última vista/filtros en localStorage entre sesiones
- **Bulk update**: editar campo en múltiples SKUs a la vez desde la tabla (lifecycle_status, family)
