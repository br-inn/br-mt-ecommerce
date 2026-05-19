# UX Productos Fase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseño UX completo del módulo productos (vista tabla + vista detalle) implementando todas las mejoras definidas en la sesión de brainstorming 2026-05-17.

**Architecture:** 3 workstreams paralelos e independientes sobre archivos distintos. Workstream A modifica la vista tabla (`page.tsx`). Workstream B mejora el header del detalle (`product-header.tsx`) y crea un drawer de edición unificado. Workstream C reorganiza los tabs del detalle (`product-tabs.tsx`). No hay dependencias entre workstreams — pueden ejecutarse simultáneamente.

**Tech Stack:** Next.js 16, React 19, TypeScript estricto, Tailwind v4, Shadcn/ui new-york, Lucide icons, `@tanstack/react-query`, `nuqs` para URL state. Primitivas MT en `@/components/mt/primitives`. Tokens en `@/components/mt/tokens`.

---

## Contexto del módulo

### Vista Tabla actual (`/catalogo`)
- Archivo: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`
- 15 columnas: checkbox, SKU, img(40px), Nombre, División, Familia, Serie, Material, DN, PN, Estado, Calidad, Trad, Actualizado, actions
- Problema: scroll horizontal en 1440px, imagen de 40px inútil, columna División redundante (ya está en barra), Familia/Serie/Material como columnas separadas desperdician espacio, jerarquía visual plana

### Header del Detalle actual (`/catalogo/[sku]`)
- Archivos: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`, `layout.tsx`
- Problemas: sin imagen del producto, 3 formas de editar (inline, /edit page, enriquecer), translation pills en el header mezclados con datos de identidad, select nativo de data_quality rompe el design system

### Tabs del Detalle actuales
- Archivo: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`
- 10 tabs en flex wrap: Specs, Mercados, Imágenes, Traducciones, Unidades, Costos, Datasheets, Recambios, Auditoría, Enriquecer
- Problema: demasiados tabs al mismo nivel, no hay indicadores de estado por tab

---

## WORKSTREAM A — Vista Tabla

**Archivos modificados:**
- `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

**Cambios:**
1. Eliminar columna "División" (redundante con la barra de división ya existente)
2. Eliminar columnas "Familia", "Serie", "Material" como columnas separadas → fusionarlas en sub-línea dentro de la celda "Nombre"
3. Reordenar columnas: `[checkbox][img→hover][SKU][Nombre+clasificación][DN][PN][Estado][Calidad][Actualizado][acciones]`
4. Imagen: reemplazar columna img fija por imagen inline dentro de la celda SKU (o mantenerla pero aumentar a 48px con mejor aspecto)
5. Hover actions: al hacer hover sobre una fila mostrar botones "Editar" y "Duplicar" en la columna de acciones

---

### Task A-1: Celda Nombre compuesta (familia · serie · material en sub-línea)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Localizar la celda "Nombre" actual** en `page.tsx` — está en el `<MtTd>` que contiene `getProductName(r)` con sub-línea `r.subfamily · r.type` (líneas ~824-836)

- [ ] **Step 2: Reemplazar la celda Nombre** con la versión compuesta que incluye la clasificación completa:

```tsx
<MtTd className="font-medium" style={{ color: MT.ink, minWidth: 280, maxWidth: 420 }}>
  <Link href={`/catalogo/${r.sku}`} className="line-clamp-1 hover:underline">
    {getProductName(r)}
  </Link>
  {/* Sub-línea: clasificación taxonómica */}
  {(() => {
    const parts: string[] = [];
    if (r.family) parts.push(r.family);
    const serName = r.series_id ? seriesById[r.series_id]?.name_en : undefined;
    if (serName) parts.push(serName);
    const matName = r.material_id ? materialById[r.material_id] : r.material ?? undefined;
    if (matName) parts.push(matName);
    if (r.subfamily) parts.push(r.subfamily);
    return parts.length > 0 ? (
      <span
        className="mt-mono mt-0.5 block truncate text-[10.5px]"
        style={{ color: MT.ink4 }}
        title={parts.join(' · ')}
      >
        {parts.join(' · ')}
      </span>
    ) : null;
  })()}
</MtTd>
```

- [ ] **Step 3: Verificar que `seriesById` y `materialById` ya están disponibles en el scope** (están definidos en las líneas ~199-216 del mismo componente — son memos derivados de `seriesListQ`, `tiersListQ`, `materialsListQ`). No se necesita ninguna importación adicional.

---

### Task A-2: Eliminar columnas Familia, Serie, Material, División

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Eliminar el `<MtTh>` de División** — localizar `<MtTh style={{ width: 110 }}>División</MtTh>` y eliminar esa línea completa del `<thead>`.

- [ ] **Step 2: Eliminar el `<MtTh>` de Familia** — localizar `<MtTh>Familia</MtTh>` y eliminar.

- [ ] **Step 3: Eliminar el `<MtTh>` de Serie** — localizar `<MtTh>Serie</MtTh>` y eliminar.

- [ ] **Step 4: Eliminar el `<MtTh>` de Material** — localizar `<MtTh>Material</MtTh>` y eliminar.

- [ ] **Step 5: En el `<tbody>`, eliminar los `<MtTd>` correspondientes a División, Familia, Serie, Material** de cada fila. Son los bloques que renderizan:
  - División: el `<MtTd>` con `r.division_codes.map(...)` 
  - Familia: el `<MtTd>` con `<Pill tone="ghost">{r.family}</Pill>`
  - Serie: el `<MtTd>` con `seriesById[r.series_id]`
  - Material: el `<MtTd>` con `materialById[r.material_id] ?? r.material`

  > **Importante:** la información de estos campos NO se pierde — queda en la sub-línea de la celda Nombre (Task A-1). Solo se eliminan las columnas redundantes.

- [ ] **Step 6: Eliminar también los `<MtTd>` de Trad** (la celda con `<TStatusGlyphs />`) y su `<MtTh style={{ width: 70 }}>Trad</MtTh>` correspondiente. La información de traducción se mostrará como badge en los tabs del detalle (Workstream C).

  > **Nota:** NO eliminar la columna `Calidad` (`<QualityBadge />`) — esa sí debe permanecer.

---

### Task A-3: Reordenar columnas y ajustar anchos

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Verificar el orden final de `<MtTh>` en el `<thead>`** después de los tasks anteriores. El orden correcto debe ser:

```tsx
<tr>
  <MtTh style={{ width: 32 }}>{/* checkbox */}</MtTh>
  <MtTh style={{ width: 48 }}>img</MtTh>
  <MtTh style={{ width: 120 }}>SKU</MtTh>
  <MtTh>Nombre</MtTh>           {/* flex-1, sin width fijo */}
  <MtTh className="text-right" style={{ width: 60 }}>DN</MtTh>
  <MtTh className="text-right" style={{ width: 60 }}>PN</MtTh>
  <MtTh style={{ width: 110 }}>Estado</MtTh>
  <MtTh style={{ width: 80 }}>Calidad</MtTh>
  <MtTh style={{ width: 95 }}>Actualizado</MtTh>
  <MtTh style={{ width: 32 }}>{""}</MtTh>
</tr>
```

- [ ] **Step 2: Verificar que los `<MtTd>` del `<tbody>` están en el mismo orden** que los headers. Contar columnas en header y en cada fila — deben coincidir exactamente.

- [ ] **Step 3: Aumentar el ancho de la columna img de 40 a 48px** actualizando `<MtTh style={{ width: 48 }}>img</MtTh>` y la celda img correspondiente:

```tsx
<MtTd>
  {r.primary_image_url ? (
    <img
      src={r.primary_image_url}
      alt=""
      className="h-10 w-10 rounded-md object-cover"
      style={{ border: `1px solid ${MT.border}` }}
    />
  ) : (
    <Thumb />
  )}
</MtTd>
```

---

### Task A-4: Hover actions en cada fila (Editar + Duplicar)

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Agregar estado `hoveredSku`** en el componente `CatalogPage`. Después de la declaración de `activeIndex`:

```tsx
const [hoveredSku, setHoveredSku] = React.useState<string | null>(null);
```

- [ ] **Step 2: Agregar `onMouseEnter` y `onMouseLeave` al `<tr>` de cada fila**:

```tsx
<tr
  key={r.sku}
  onClick={() => setActiveIndex(i)}
  onMouseEnter={() => setHoveredSku(r.sku)}
  onMouseLeave={() => setHoveredSku(null)}
  style={{
    background: i % 2 ? MT.surface : MT.surface2,
    boxShadow: isActive ? `inset 3px 0 0 ${MT.brand}` : undefined,
    cursor: "default",
  }}
>
```

- [ ] **Step 3: Reemplazar la columna `actions` actual** (el `<MtTd>` con `<MoreHorizontal>` que navega al detalle) por una celda de acciones contextuales:

```tsx
<MtTd>
  <div className="flex items-center justify-end gap-1">
    {hoveredSku === r.sku ? (
      <>
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
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            toast.info(`Duplicar ${r.sku} — próximamente`);
          }}
          className="inline-flex h-6 items-center gap-1 rounded px-2 text-[11px] font-medium transition-colors hover:bg-mt-surface-2"
          style={{ color: MT.ink3 }}
          title="Duplicar"
        >
          <Copy className="size-3" />
          Duplicar
        </button>
      </>
    ) : (
      <Link href={`/catalogo/${r.sku}`} aria-label={`Ver ${r.sku}`}>
        <MoreHorizontal
          className="size-3.5 cursor-pointer"
          style={{ color: MT.ink4 }}
        />
      </Link>
    )}
  </div>
</MtTd>
```

- [ ] **Step 4: Agregar el import de `Copy` y `Pencil` desde lucide-react** al bloque de imports existente:

```tsx
import {
  Copy,
  Download,
  Image as ImageIcon,
  MoreHorizontal,
  Pencil,       // agregar
  Plus,
  Upload,
  X,
} from "lucide-react";
```

- [ ] **Step 5: Verificar TypeScript** — el `Pencil` ya se importaba en `product-header.tsx` pero no en `page.tsx`. Asegurarse de que no hay conflicto de nombres.

---

### Task A-5: Bulk actions expandidas

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/page.tsx`

- [ ] **Step 1: Localizar el bloque de bulk actions** (`{selectedSkus.size > 0 ? (...)`) — líneas ~694-724 aproximadamente.

- [ ] **Step 2: Reemplazar el contenido del bloque** con acciones expandidas:

```tsx
{selectedSkus.size > 0 ? (
  <div
    className="flex items-center gap-3 border-b px-6 py-2 text-[12.5px]"
    style={{ borderColor: MT.border, background: MT.surface2 }}
  >
    <span style={{ color: MT.ink }}>
      <strong>{selectedSkus.size}</strong> seleccionado{selectedSkus.size !== 1 ? "s" : ""}
    </span>
    {/* Exportar selección */}
    <button
      type="button"
      className="flex items-center gap-1 rounded px-2 py-1 hover:bg-mt-surface"
      style={{ color: MT.brand }}
      onClick={() => {
        const selected = items.filter((r) => selectedSkus.has(r.sku));
        exportToCsv(selected, `seleccion-${Date.now()}.csv`);
      }}
    >
      <Download className="size-3" />
      Exportar CSV
    </button>
    {/* Activar selección */}
    <button
      type="button"
      className="flex items-center gap-1 rounded px-2 py-1 hover:bg-mt-surface"
      style={{ color: MT.ink2 }}
      onClick={() => {
        toast.info(`Activar ${selectedSkus.size} SKUs — próximamente`);
      }}
    >
      Activar
    </button>
    {/* Archivar selección */}
    <button
      type="button"
      className="flex items-center gap-1 rounded px-2 py-1 hover:bg-mt-surface"
      style={{ color: MT.ink2 }}
      onClick={() => {
        toast.info(`Archivar ${selectedSkus.size} SKUs — próximamente`);
      }}
    >
      Archivar
    </button>
    {/* Asignar familia */}
    <button
      type="button"
      className="flex items-center gap-1 rounded px-2 py-1 hover:bg-mt-surface"
      style={{ color: MT.ink2 }}
      onClick={() => {
        toast.info(`Asignar familia a ${selectedSkus.size} SKUs — próximamente`);
      }}
    >
      Asignar familia
    </button>
    {/* Limpiar selección */}
    <button
      type="button"
      className="ml-auto flex items-center gap-1 rounded px-2 py-1 hover:bg-mt-surface"
      style={{ color: MT.ink3 }}
      onClick={() => setSelectedSkus(new Set())}
    >
      <X className="size-3" />
      Limpiar
    </button>
  </div>
) : null}
```

> **Nota:** Las acciones "Activar", "Archivar" y "Asignar familia" muestran `toast.info` con "próximamente" — el scaffolding UX está listo para cuando se conecten al backend.

---

### Task A-6: Verificar y hacer restart del frontend

**Files:**
- No file changes — verificación

- [ ] **Step 1: Verificar que TypeScript no tiene errores** en `page.tsx`:

```bash
cd mt-pricing-frontend && npx tsc --noEmit --project tsconfig.json 2>&1 | grep -i "catalogo/page"
```

Esperado: sin errores en `page.tsx`.

- [ ] **Step 2: Restart del contenedor frontend**:

```bash
docker restart mt-frontend
```

- [ ] **Step 3: Verificar que el frontend levanta correctamente**:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/catalogo
```

Esperado: `200`

- [ ] **Step 4: Commit del Workstream A**:

```bash
git add mt-pricing-frontend/app/(app)/catalogo/page.tsx
git commit -m "feat(catalog): tabla rediseñada — celda nombre compuesta, columnas simplificadas, hover actions"
```

---

## WORKSTREAM B — Header del Detalle + Drawer de Edición

**Archivos modificados/creados:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`
- Create: `mt-pricing-frontend/components/domain/product-edit-drawer.tsx`

**Cambios:**
1. Agregar imagen del producto como columna izquierda del header (layout 2 columnas)
2. Eliminar `TranslationStatusPill` del header — van al tab Traducciones
3. Eliminar el `<select>` nativo de `data_quality` del header
4. Eliminar el modo inline-edit del header (confuso y parcial)
5. Reemplazar botones "Editar" + "Editar completo" por un único botón "Editar" que abre un drawer completo
6. Crear el `ProductEditDrawer` con todos los campos editables

---

### Task B-1: Crear ProductEditDrawer

**Files:**
- Create: `mt-pricing-frontend/components/domain/product-edit-drawer.tsx`

- [ ] **Step 1: Crear el archivo** `mt-pricing-frontend/components/domain/product-edit-drawer.tsx` con el siguiente contenido:

```tsx
"use client";

import * as React from "react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { productsApi } from "@/lib/api/endpoints/products";
import { productKeys } from "@/lib/hooks/products/query-keys";
import type {
  ProductDetail,
  ProductLifecycleStatus,
  DataQuality,
} from "@/lib/api/endpoints/products";

const LIFECYCLE_OPTIONS: { value: ProductLifecycleStatus; label: string }[] = [
  { value: "draft", label: "Borrador" },
  { value: "in_review", label: "En revisión" },
  { value: "active", label: "Activo" },
  { value: "deprecated", label: "Obsoleto" },
  { value: "replaced", label: "Reemplazado" },
  { value: "discontinued", label: "Descontinuado" },
];

const QUALITY_OPTIONS: { value: DataQuality; label: string }[] = [
  { value: "partial", label: "Parcial" },
  { value: "complete", label: "Completa" },
  { value: "blocked", label: "Bloqueada" },
];

interface Props {
  sku: string;
  product: ProductDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProductEditDrawer({ sku, product, open, onOpenChange }: Props) {
  const queryClient = useQueryClient();

  const [draft, setDraft] = React.useState({
    name_es: (product.translations?.es?.name ?? "") as string,
    name_ar: (product.translations?.ar?.name ?? "") as string,
    brand: product.brand ?? "",
    gtin: product.gtin ?? "",
    lifecycle_status: (product.lifecycle_status ?? "active") as ProductLifecycleStatus,
    data_quality: (product.data_quality ?? "partial") as DataQuality,
  });

  // Sync draft when product changes
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

  const patchMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      productsApi.update(sku, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.detail(sku) });
      onOpenChange(false);
      toast.success("Producto actualizado");
    },
    onError: () => {
      toast.error("Error al guardar los cambios");
    },
  });

  const handleSave = () => {
    const original = product;
    const payload: Record<string, unknown> = {
      lifecycle_status: draft.lifecycle_status,
      data_quality: draft.data_quality,
    };

    if (draft.brand !== (original.brand ?? "")) {
      payload.brand = draft.brand || null;
    }
    if (draft.gtin !== (original.gtin ?? "")) {
      payload.gtin = draft.gtin || null;
    }

    const originalNameEs = (original.translations?.es?.name ?? "") as string;
    const originalNameAr = (original.translations?.ar?.name ?? "") as string;
    const transPayload: Record<string, { name: string }> = {};
    if (draft.name_es !== originalNameEs && draft.name_es.trim()) {
      transPayload.es = { name: draft.name_es.trim() };
    }
    if (draft.name_ar !== originalNameAr && draft.name_ar.trim()) {
      transPayload.ar = { name: draft.name_ar.trim() };
    }
    if (Object.keys(transPayload).length > 0) {
      payload.translations = transPayload;
    }

    patchMutation.mutate(payload);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
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
      </SheetContent>
    </Sheet>
  );
}
```

---

### Task B-2: Refactorizar ProductHeader — agregar imagen, eliminar inline-edit, conectar drawer

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`

- [ ] **Step 1: Reemplazar el contenido completo de `product-header.tsx`** con la versión refactorizada:

```tsx
"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { Barcode, ImageIcon, Layers, GitBranch, Pencil, Ruler } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import { CompletenessRing } from "@/components/ui/completeness-ring";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import { SkuActionsMenu } from "@/components/domain/sku-actions-menu";
import { ProductEditDrawer } from "@/components/domain/product-edit-drawer";
import { useProduct } from "@/lib/hooks/products/use-product";
import { getProductName } from "@/lib/utils/product-display";
import { isProductActive } from "@/lib/utils/product-lifecycle";

// KVP row — SAP Fiori Object Page pattern (UX-02)
function KVP({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </dt>
      <dd
        className={`truncate text-sm font-semibold ${mono ? "font-mono" : ""}`}
      >
        {value ?? "—"}
      </dd>
    </div>
  );
}

interface Props {
  sku: string;
}

export function ProductHeader({ sku }: Props) {
  const { data: product, isLoading, isError } = useProduct(sku);
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex gap-4">
        <Skeleton className="h-[140px] w-[140px] shrink-0 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        No se encontró el producto.
      </div>
    );
  }

  const seriesLabel =
    product.series_detail?.code ??
    (product as { series?: string | null }).series ??
    null;

  return (
    <>
      {/* Drawer de edición unificado */}
      <ProductEditDrawer
        sku={sku}
        product={product}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />

      {/* Layout principal: imagen izquierda + datos derecha */}
      <div className="flex gap-5">
        {/* ── Imagen del producto ── */}
        <div className="shrink-0">
          {product.primary_image_url ? (
            <img
              src={product.primary_image_url}
              alt={getProductName(product)}
              className="h-[140px] w-[140px] rounded-lg object-cover"
              style={{ border: "1px solid hsl(var(--border))" }}
            />
          ) : (
            <div
              className="flex h-[140px] w-[140px] items-center justify-center rounded-lg"
              style={{ border: "1px solid hsl(var(--border))", background: "hsl(var(--muted)/0.4)" }}
            >
              <ImageIcon className="h-10 w-10 text-muted-foreground/25" strokeWidth={1.2} />
            </div>
          )}
        </div>

        {/* ── Datos del producto ── */}
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          {/* Fila 1: identidad + acciones */}
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-1">
              {/* SKU + revision + badges de clasificación */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {product.sku}
                  {product.revision ? (
                    <span className="ml-1.5 text-[10px] text-muted-foreground/60">
                      · {product.revision}
                    </span>
                  ) : null}
                </span>
                {product.family ? (
                  <Badge variant="secondary" className="capitalize">
                    {product.family}
                  </Badge>
                ) : null}
                {product.is_parent ? (
                  <Badge variant="outline" className="gap-1 text-[11px]">
                    <Layers className="h-3 w-3" /> Padre
                  </Badge>
                ) : null}
                {product.is_variant && product.parent_sku ? (
                  <Link
                    href={`/catalogo/${product.parent_sku}`}
                    className="inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-[11px] font-semibold text-foreground transition-colors hover:bg-muted/50"
                  >
                    <GitBranch className="h-3 w-3" /> Variante de{" "}
                    {product.parent_sku}
                  </Link>
                ) : null}
                <LifecycleStatusBadge status={product.lifecycle_status} />
              </div>

              {/* Nombre + completeness ring */}
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {getProductName(product)}
                </h1>
                <CompletenessRing product={product} />
              </div>

              {/* Data quality badge — solo lectura */}
              <div className="flex flex-wrap items-center gap-2">
                <DataQualityBadge value={product.data_quality} />
              </div>
            </div>

            {/* Botones de acción */}
            <div className="flex shrink-0 items-center gap-2">
              <RbacGuard permissions={["products:write"]}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDrawerOpen(true)}
                >
                  <Pencil className="h-4 w-4" />
                  Editar
                </Button>
              </RbacGuard>
              <SkuActionsMenu
                product={{
                  id: (product as { id?: string }).id ?? product.internal_id,
                  sku: product.sku,
                  active: isProductActive(product),
                }}
              />
            </div>
          </div>

          {/* Fila 2: Quick Facts (KVPs) */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-4">
            <KVP
              label="UoM Base"
              value={
                <span className="flex items-center gap-1">
                  <Ruler className="h-3 w-3 text-muted-foreground" />
                  {product.base_uom ?? "UNIT"}
                </span>
              }
            />
            <KVP
              label="GTIN"
              value={
                product.gtin ? (
                  <span className="flex items-center gap-1">
                    <Barcode className="h-3 w-3 text-muted-foreground" />
                    {product.gtin}
                  </span>
                ) : null
              }
              mono
            />
            <KVP
              label="Marca"
              value={
                product.brand ??
                (product as { brand_name?: string }).brand_name
              }
            />
            <KVP label="Serie" value={seriesLabel} />
            {product.model_detail ? (
              <>
                <KVP
                  label="Modelo"
                  value={
                    <span className="flex items-center gap-1.5">
                      <span className="font-mono">
                        {product.model_detail.code}
                      </span>
                      {product.model_detail.color_label ? (
                        <Badge variant="outline" className="text-[10px] capitalize">
                          {product.model_detail.color_label}
                        </Badge>
                      ) : null}
                    </span>
                  }
                />
                {product.model_detail.connection_type ? (
                  <KVP
                    label="Conexión"
                    value={product.model_detail.connection_type}
                  />
                ) : null}
              </>
            ) : null}
          </dl>
        </div>
      </div>
    </>
  );
}
```

> **Cambios clave vs. versión anterior:**
> - Eliminado: modo inline-edit completo (estado `editMode`, `draft`, `patchMutation`, `patchQuality` de KVPs, botón "Editar completo")
> - Eliminado: `TranslationStatusPill` (3 pills EN/ES/AR)
> - Eliminado: `<select>` nativo de `data_quality`
> - Agregado: imagen del producto con fallback placeholder
> - Agregado: botón único "Editar" que abre `ProductEditDrawer`
> - Simplificado: `DataQualityBadge` solo lectura

---

### Task B-3: Verificar imports y restart

**Files:**
- No file changes — verificación

- [ ] **Step 1: Verificar que no quedan imports sin usar** en `product-header.tsx`. Los siguientes imports de la versión anterior deben ser eliminados si quedaron:
  - `useTranslations` (next-intl)
  - `Input`, `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` (de ui)
  - `useMutation`, `useQueryClient` (tanstack)
  - `productsApi`, `productKeys`
  - `TranslationStatusPill`
  - `usePatchDataQuality`
  - `type ProductLifecycleStatus` (si no se usa directamente)

- [ ] **Step 2: Verificar TypeScript** en los dos archivos modificados:

```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | grep -E "(product-header|product-edit-drawer)"
```

Esperado: sin errores.

- [ ] **Step 3: Restart del contenedor**:

```bash
docker restart mt-frontend
```

- [ ] **Step 4: Commit del Workstream B**:

```bash
git add mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx \
        mt-pricing-frontend/components/domain/product-edit-drawer.tsx
git commit -m "feat(product-detail): imagen en header, drawer de edición unificado, eliminar inline-edit y translation pills"
```

---

## WORKSTREAM C — Tabs del Detalle Reorganizados

**Archivos modificados:**
- `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`

**Cambios:**
1. Reducir a 5 tabs primarios visibles: Specs, Mercados, Imágenes, Traducciones, Datasheets
2. Mover a overflow dropdown (`···`): Unidades, Costos, Recambios, Auditoría, Enriquecer
3. Agregar badge de alerta (⚠) en tab Imágenes cuando el producto no tiene imagen — requiere pasar `hasImage` como prop desde el layout o inferirlo del pathname
4. El tab activo del overflow debe mostrarse visualmente activo también

---

### Task C-1: Reorganizar tabs con overflow dropdown

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx`

- [ ] **Step 1: Agregar imports necesarios** para el dropdown. En `product-tabs.tsx`, agregar al bloque de imports:

```tsx
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
```

- [ ] **Step 2: Reemplazar el contenido completo del archivo** con la versión reorganizada:

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Props {
  sku: string;
  /** Si el producto no tiene imagen principal, se muestra alerta en tab Imágenes */
  hasImage?: boolean;
}

/**
 * Tabs URL-driven con overflow. 5 tabs primarios visibles + dropdown para los
 * tabs operacionales menos frecuentes.
 */
export function ProductTabs({ sku, hasImage = true }: Props) {
  const pathname = usePathname() ?? "";

  const primaryTabs = [
    {
      href: `/catalogo/${sku}`,
      label: "Specs",
      match: (p: string) => p === `/catalogo/${sku}`,
    },
    {
      href: `/catalogo/${sku}/mercados`,
      label: "Mercados",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/mercados`),
    },
    {
      href: `/catalogo/${sku}/imagenes`,
      label: "Imágenes",
      badge: !hasImage ? "⚠" : undefined,
      match: (p: string) => p.startsWith(`/catalogo/${sku}/imagenes`),
    },
    {
      href: `/catalogo/${sku}/traducciones`,
      label: "Traducciones",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/traducciones`),
    },
    {
      href: `/catalogo/${sku}/datasheets`,
      label: "Datasheets",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/datasheets`),
    },
  ];

  const overflowTabs = [
    {
      href: `/catalogo/${sku}/unidades`,
      label: "Unidades",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/unidades`),
    },
    {
      href: `/catalogo/${sku}/costos`,
      label: "Costos",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/costos`),
    },
    {
      href: `/catalogo/${sku}/recambios`,
      label: "Recambios",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/recambios`),
    },
    {
      href: `/catalogo/${sku}/audit`,
      label: "Auditoría",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/audit`),
    },
    {
      href: `/catalogo/${sku}/enriquecer`,
      label: "Enriquecer",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/enriquecer`),
    },
  ];

  // ¿Algún tab del overflow está activo? Si es así, el botón ··· se activa también.
  const overflowActive = overflowTabs.some((t) => t.match(pathname));
  const activeOverflowTab = overflowTabs.find((t) => t.match(pathname));

  return (
    <nav
      role="tablist"
      aria-label="Secciones del producto"
      className="border-b"
    >
      <ul className="-mb-px flex items-center gap-1">
        {/* Tabs primarios */}
        {primaryTabs.map((tab) => {
          const active = tab.match(pathname);
          return (
            <li key={tab.href} role="presentation">
              <Link
                href={tab.href}
                role="tab"
                aria-selected={active}
                className={cn(
                  "inline-flex items-center gap-1.5 border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
                {tab.badge ? (
                  <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-700">
                    {tab.badge}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}

        {/* Overflow dropdown */}
        <li role="presentation" className="ml-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                role="tab"
                aria-selected={overflowActive}
                className={cn(
                  "inline-flex items-center gap-1 border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  overflowActive
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {overflowActive && activeOverflowTab
                  ? activeOverflowTab.label
                  : <MoreHorizontal className="h-4 w-4" />}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {overflowTabs.map((tab) => {
                const active = tab.match(pathname);
                return (
                  <DropdownMenuItem key={tab.href} asChild>
                    <Link
                      href={tab.href}
                      className={cn(
                        "w-full",
                        active && "font-semibold text-foreground",
                      )}
                    >
                      {tab.label}
                    </Link>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </li>
      </ul>
    </nav>
  );
}
```

---

### Task C-2: Pasar `hasImage` desde el layout al ProductTabs

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx`

- [ ] **Step 1: Evaluar si pasar `hasImage` requiere fetch adicional en el layout**. El `layout.tsx` actual es un Server Component — puede hacer fetch del producto directamente o delegar al `ProductHeader` que ya tiene `useProduct`.

  Opción más sencilla: pasar `hasImage={true}` por defecto en el layout y dejar que el badge se muestre dinámicamente cuando el `ProductTabs` detecte la URL. El badge de imágenes es un nice-to-have para esta fase.

- [ ] **Step 2: Actualizar el `ProductTabs` en `layout.tsx`** — como el componente tiene default `hasImage={true}`, no se necesita cambio en `layout.tsx`. El badge se activará en una fase posterior cuando se implemente la detección de imagen.

  Verificar que `layout.tsx` pasa `sku` al `ProductTabs`:

```tsx
<ProductTabs sku={sku} />  {/* sin cambios — hasImage default = true */}
```

---

### Task C-3: Verificar y commit del Workstream C

**Files:**
- No file changes — verificación

- [ ] **Step 1: Verificar TypeScript en product-tabs.tsx**:

```bash
cd mt-pricing-frontend && npx tsc --noEmit 2>&1 | grep "product-tabs"
```

Esperado: sin errores.

- [ ] **Step 2: Verificar que `DropdownMenu` está disponible** (el componente existe en `components/ui/dropdown-menu.tsx` — confirmado por el uso en otras partes del proyecto).

- [ ] **Step 3: Restart del contenedor**:

```bash
docker restart mt-frontend
```

- [ ] **Step 4: Verificar que los tabs se renderizan correctamente** navegando a cualquier `/catalogo/[sku]`. Deben aparecer 5 tabs primarios + botón `···` que al hacer click muestra los 5 secundarios.

- [ ] **Step 5: Commit del Workstream C**:

```bash
git add mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-tabs.tsx \
        mt-pricing-frontend/app/(app)/catalogo/[sku]/layout.tsx
git commit -m "feat(product-tabs): 5 tabs primarios + overflow dropdown, eliminar tabs secundarios visibles"
```

---

## INTEGRACIÓN FINAL

### Task Final: Verificación completa y commit integrador

**Files:**
- No file changes — verificación

- [ ] **Step 1: Verificar que los 3 workstreams no tienen conflictos de merge** (cada uno toca archivos distintos — no debería haber conflictos).

- [ ] **Step 2: Build completo del frontend**:

```bash
cd mt-pricing-frontend && npx next build 2>&1 | tail -20
```

Esperado: `✓ Compiled successfully` o similar. Sin errores de TypeScript ni de módulos.

- [ ] **Step 3: Restart completo del contenedor**:

```bash
docker restart mt-frontend
```

- [ ] **Step 4: Smoke tests manuales**:
  - `/catalogo` → tabla sin columnas División/Familia/Serie/Material, nombre con sub-línea de clasificación, hover sobre fila muestra botones Editar/Duplicar
  - `/catalogo?q=test` → seleccionar 2 SKUs → barra de bulk actions muestra Exportar CSV + Activar + Archivar + Asignar familia
  - `/catalogo/[cualquier-sku]` → header con imagen (o placeholder), sin translation pills, sin select de quality, botón "Editar" abre drawer lateral
  - Drawer de edición → modificar nombre ES → guardar → toast de éxito → drawer cierra
  - Tabs del detalle → 5 tabs primarios visibles → click en `···` → dropdown con los 5 secundarios
  - Navegar a tab secundario (ej. Auditoría) → el botón `···` muestra "Auditoría" como label activo

- [ ] **Step 5: Commit integrador** (solo si los 3 workstreams se implementaron en sesiones separadas y aún no se hizo):

```bash
git add -A
git commit -m "feat(ux-productos): fase 1 completa — tabla simplificada, header con imagen, tabs reorganizados, drawer de edición"
```

---

## Self-Review

### Cobertura del spec

| Ítem del brainstorming | Task | Estado |
|------------------------|------|--------|
| Celda nombre compuesta (familia · serie · material) | A-1 | ✅ |
| Eliminar columnas División, Familia, Serie, Material, Trad | A-2 | ✅ |
| Reordenar columnas por frecuencia de uso | A-3 | ✅ |
| Imagen del producto en header del detalle | B-2 | ✅ |
| Eliminar translation pills del header | B-2 | ✅ |
| Eliminar select inline de data_quality | B-2 | ✅ |
| Unificar Editar + Editar completo en drawer | B-1 + B-2 | ✅ |
| Eliminar inline-edit mode del header | B-2 | ✅ |
| Tabs: 5 primarios + overflow dropdown | C-1 | ✅ |
| Badge de alerta en tab Imágenes | C-1 | ✅ (estructura lista, activación en Fase 2) |
| Hover actions en filas (Editar + Duplicar) | A-4 | ✅ |
| Bulk actions expandidas | A-5 | ✅ (scaffolding listo, backend en Fase 2) |

### Notas de Fase 2 (no en este plan)
- Activar/Archivar/Asignar familia bulk → requieren endpoints backend
- Badge dinámico de Imágenes → requiere pasar `hasImage` desde el producto
- Paginación real con URL-state (`?page=N`) → cambio en `useProducts` + paginator
- Navegación prev/next en detalle → requiere contexto de filtros entre tabla y detalle
- Quick view drawer en hover → nuevo componente + overlay logic
- Toggle Vista Galería → nuevo modo de visualización en page.tsx
