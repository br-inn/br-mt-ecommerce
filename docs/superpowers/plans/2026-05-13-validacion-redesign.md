# Validación Matches — Rediseño de Pantalla

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar `/catalogo/validacion` con split-view MT ↔ Amazon, cola de SKUs colapsable y cards de candidatos — de modo que un validador tenga "todo lo suficiente para validar correctamente en una sola pantalla."

**Architecture:** Extraer 3 sub-componentes (`SkuQueuePanel`, `MtProductPanel`, `CandidateCard`) co-localizados en `_components/` y reescribir `page.tsx` para ensamblarlos. Sin cambios de backend — todos los datos disponibles vía hooks existentes.

**Tech Stack:** Next.js 16, React 19, TypeScript strict, Tailwind v4, `@tanstack/react-query`, Lucide icons, MT design tokens.

---

## File Map

| Acción | Archivo |
|--------|---------|
| Modify | `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx` |
| Create | `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx` |
| Create | `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/mt-product-panel.tsx` |
| Create | `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/sku-queue-panel.tsx` |

---

## Task 1: Quick wins — inline en page.tsx

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

Tres mejoras independientes que no tocan la arquitectura.

- [ ] **Step 1: Eliminar texto de deuda técnica (E1)**

En `page.tsx`, línea ~503, buscar y eliminar la línea:
```tsx
// ANTES:
<div className="mt-0.5 text-[11px]" style={{ color: MT.ink3 }}>
  Ordenados por score descendente · Stubs Sprint 3 (scraper Amazon real en S4)
</div>

// DESPUÉS: eliminar ese <div> completo
```

- [ ] **Step 2: Reducir header a barra delgada (M4)**

Reemplazar el bloque `{/* Workflow header */}` (líneas ~348–378) por:

```tsx
{/* Workflow header — barra delgada */}
<div
  className="flex h-9 items-center justify-between gap-4 border-b px-5"
  style={{ background: MT.surface2, borderColor: MT.border }}
>
  <div className="flex items-center gap-2">
    <span className="mt-mono text-[10.5px] uppercase tracking-[1px]" style={{ color: MT.ink4 }}>
      Validación
    </span>
    <span style={{ color: MT.border }}>›</span>
    <span className="mt-mono text-[12px] font-semibold" style={{ color: MT.ink }}>
      {sku === "—" ? "—" : sku}
    </span>
    {queue.length > 0 && (
      <span
        className="ml-1 inline-flex h-5 items-center rounded-[4px] border px-1.5 text-[10.5px] font-medium"
        style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink3 }}
      >
        {queue.length - clampedIndex} pendientes
      </span>
    )}
  </div>
  <MtButton
    size="sm"
    icon={<RefreshCcw className="size-3" />}
    onClick={() => queue.length > 0 && refresh.mutate(sku)}
    disabled={refresh.isPending || queue.length === 0}
  >
    {refresh.isPending ? "Re-scraping…" : "Re-scrape"}
  </MtButton>
</div>
```

- [ ] **Step 3: Agregar contadores a los tabs de filtro (P3)**

`FilterChip` ya acepta prop `count`. Actualizar el array `FILTER_TABS` y el render para pasar contadores:

```tsx
// Calcular contadores fuera del render
const pendingCount = items.filter((c) => c.status === "pending").length;
const validatedCount = items.filter((c) => c.status === "validated").length;
const discardedCount = items.filter((c) => c.status === "discarded").length;
const tabCounts: Record<MatchStatus | "all", number | undefined> = {
  all: total ?? undefined,
  pending: pendingCount || undefined,
  validated: validatedCount || undefined,
  discarded: discardedCount || undefined,
};

// En el render de FILTER_TABS:
{FILTER_TABS.map((t) => (
  <button
    key={t.l}
    type="button"
    onClick={() => setStatusFilter(t.status)}
    className="cursor-pointer"
  >
    <FilterChip
      label={t.l}
      count={tabCounts[t.status]}
      active={statusFilter === t.status}
    />
  </button>
))}
```

- [ ] **Step 4: Reiniciar el frontend y verificar visualmente**

```powershell
docker restart mt-frontend
```

Abrir `http://localhost:8080/catalogo/validacion` y verificar:
- Header ocupa ~36px (antes ~90px)
- Tabs muestran contadores: `Pendientes (N)`
- No hay texto "Stubs Sprint 3" en el panel de candidatos

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "fix(validacion): quick wins — header delgado, contadores en tabs, eliminar texto deuda técnica"
```

---

## Task 2: CandidateCard — reemplaza CandidateRow

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

Card horizontal con foto, specs, precio, score semáforo y botones de decisión inline.

- [ ] **Step 1: Crear `_components/candidate-card.tsx`**

```tsx
"use client";

import * as React from "react";
import { Check, ExternalLink, X, Clock } from "lucide-react";
import Image from "next/image";
import { MtButton, ScorePill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { MatchCandidate } from "@/lib/api/endpoints/matches";

const fmtAED = (n: number | null) =>
  n == null
    ? "—"
    : `AED ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n)}`;

const KIND_LABELS: Record<MatchCandidate["kind"], string> = {
  peer: "Peer fabricante",
  drop: "Distribuidor",
  unknown: "Sin clasificar",
};

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5 text-[11px]">
      <span className="w-14 shrink-0 text-right" style={{ color: MT.ink4 }}>
        {label}
      </span>
      <span
        className={/[0-9]/.test(value) ? "mt-mono font-semibold" : "font-medium"}
        style={{ color: MT.ink2 }}
      >
        {value}
      </span>
    </div>
  );
}

export function CandidateCard({
  candidate,
  onValidate,
  onDiscard,
  pending,
}: {
  candidate: MatchCandidate;
  onValidate: () => void;
  onDiscard: () => void;
  pending: boolean;
}) {
  const { id, brand, external_id, title, kind, price_aed, score, status, delivery_text, specs_jsonb } =
    candidate;
  const specs = specs_jsonb as Record<string, string | null | undefined>;
  const priceNum = price_aed === null ? null : Number(price_aed);

  const isVal = status === "validated";
  const isDis = status === "discarded";

  const borderLeft = isVal ? MT.success : isDis ? MT.danger : "transparent";
  const bg = isVal ? "#F4FBF6" : isDis ? "#FBF5F4" : MT.surface;

  return (
    <div
      className="relative flex items-start gap-3 rounded-lg border p-3.5 transition-shadow hover:shadow-sm"
      style={{ background: bg, borderColor: MT.border }}
    >
      {/* Left accent bar */}
      <span
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-lg"
        style={{ background: borderLeft }}
      />

      {/* Foto Amazon */}
      <div
        className="mt-1 flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-[6px] border"
        style={{ background: MT.surface3, borderColor: MT.border }}
      >
        {/* Placeholder hasta que el scraper traiga URLs de imagen */}
        <span className="mt-mono text-[9px] uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
          foto
        </span>
      </div>

      {/* Info principal */}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="text-[13px] font-semibold" style={{ color: MT.ink }}>
            {brand ?? "—"}
          </span>
          <span
            className="inline-flex h-4 items-center rounded-[3px] border px-1.5 text-[10px] font-medium"
            style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink3 }}
          >
            {KIND_LABELS[kind]}
          </span>
          <span className="mt-mono text-[10px]" style={{ color: MT.ink4 }}>
            {external_id}
          </span>
        </div>
        <p className="mb-2 text-[11.5px] leading-[1.35]" style={{ color: MT.ink3 }}>
          {title}
        </p>

        {/* Specs grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
          <SpecRow label="Material" value={String(specs?.material ?? "—")} />
          <SpecRow label="Norma" value={String(specs?.norma ?? "—")} />
          <SpecRow label="Tipo" value={String(specs?.valve_type ?? specs?.type ?? "—")} />
          <SpecRow label="PN" value={String(specs?.pn ?? "—")} />
          <SpecRow label="Rosca" value={String(specs?.thread ?? "—")} />
        </div>
      </div>

      {/* Precio + score */}
      <div className="flex w-28 shrink-0 flex-col items-end gap-1.5 pt-0.5">
        <div className="mt-mono text-[15px] font-bold tracking-[-0.2px]" style={{ color: MT.ink }}>
          {fmtAED(priceNum)}
        </div>
        <ScorePill score={score} size="lg" />
        {delivery_text && (
          <span className="text-right text-[10.5px] leading-tight" style={{ color: MT.ink3 }}>
            {delivery_text}
          </span>
        )}
      </div>

      {/* Decisión */}
      <div className="flex w-36 shrink-0 flex-col items-stretch gap-1.5 pt-0.5">
        {isVal ? (
          <span
            className="inline-flex h-7 items-center justify-center gap-1.5 rounded-[5px] border text-[11.5px] font-semibold"
            style={{ color: MT.success, background: MT.successSoft, borderColor: MT.successBorder }}
          >
            <Check className="size-3" strokeWidth={2.5} /> Validado
          </span>
        ) : isDis ? (
          <span
            className="inline-flex h-7 items-center justify-center gap-1.5 rounded-[5px] border text-[11.5px] font-semibold"
            style={{ color: MT.danger, background: MT.dangerSoft, borderColor: MT.dangerBorder }}
          >
            <X className="size-3" strokeWidth={2.5} /> Descartado
          </span>
        ) : (
          <>
            <button
              type="button"
              onClick={onValidate}
              disabled={pending}
              className="inline-flex h-7 cursor-pointer items-center justify-center gap-1.5 rounded-[5px] border px-2.5 text-[12px] font-semibold text-white disabled:opacity-50"
              style={{ background: MT.brand, borderColor: MT.brand }}
            >
              <Check className="size-3" strokeWidth={2.5} /> Validar
            </button>
            <button
              type="button"
              onClick={onDiscard}
              disabled={pending}
              className="inline-flex h-6 cursor-pointer items-center justify-center gap-1 rounded-[5px] border text-[11px] font-medium disabled:opacity-50"
              style={{ color: MT.ink3, borderColor: MT.border }}
            >
              <X className="size-3" /> Descartar
            </button>
          </>
        )}
        <a
          href={`https://www.amazon.ae/dp/${external_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-mono inline-flex h-5 items-center justify-center gap-1 text-[10px] hover:underline"
          style={{ color: MT.ink4 }}
        >
          <ExternalLink className="size-3" /> Amazon UAE
        </a>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Reemplazar `<table>` en page.tsx por lista de `CandidateCard`**

En `page.tsx`, importar `CandidateCard`:
```tsx
import { CandidateCard } from "./_components/candidate-card";
```

Reemplazar el bloque `<table>...</table>` completo por:
```tsx
<div className="flex flex-col gap-2 p-3">
  {isLoading
    ? Array.from({ length: 5 }).map((_, i) => (
        <div key={`sk-${i}`} className="h-[112px] animate-pulse rounded-lg" style={{ background: MT.surface3 }} />
      ))
    : items.map((c) => (
        <CandidateCard
          key={c.id}
          candidate={c}
          pending={mutating}
          onValidate={() => validate.mutate(c.id)}
          onDiscard={() => discard.mutate({ id: c.id })}
        />
      ))}
</div>
```

También eliminar los imports de `Image as ImageIcon` y los componentes `SpecLine`, `CandidateRow`, `CompetitorTag` que ya no se usan.

- [ ] **Step 3: Verificar en browser**

```powershell
docker restart mt-frontend
```

Abrir `http://localhost:8080/catalogo/validacion`. Verificar:
- Candidatos se muestran como cards horizontales (no tabla)
- Botones Validar/Descartar están dentro de cada card
- Score visible con colores semáforo
- Cards con borde izquierdo verde/rojo para validados/descartados

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/_components/candidate-card.tsx
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): reemplaza tabla por CandidateCard — specs grid, score semáforo, botones inline"
```

---

## Task 3: MtProductPanel — ficha MT fija

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/mt-product-panel.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

Panel izquierdo fijo que muestra la ficha completa del producto MT para comparar con los candidatos.

- [ ] **Step 1: Crear `_components/mt-product-panel.tsx`**

```tsx
"use client";

import * as React from "react";
import Link from "next/link";
import { FileText, History } from "lucide-react";
import Image from "next/image";
import { MtButton, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { useProduct } from "@/lib/hooks/products/use-product";
import { useProductImages } from "@/lib/hooks/products/use-product-images";
import { MtSkeleton } from "@/components/mt/states";

function SpecRow({ label, value }: { label: string; value: string }) {
  const isNumeric = /[0-9]/.test(value);
  return (
    <div className="flex items-baseline gap-1.5 py-[2px] text-[11px]">
      <span className="w-14 shrink-0 text-right" style={{ color: MT.ink4 }}>
        {label}
      </span>
      <span
        className={isNumeric ? "mt-mono font-semibold" : "font-medium"}
        style={{ color: MT.ink2 }}
      >
        {value || "—"}
      </span>
    </div>
  );
}

export function MtProductPanel({ sku }: { sku: string }) {
  const { data: product, isLoading } = useProduct(sku);
  const { data: images } = useProductImages(product?.internal_id);

  const primaryImage = images?.find((img) => img.is_primary && img.kind === "photo");
  const imageUrl = primaryImage?.urls?.thumb_400 ?? primaryImage?.urls?.original ?? null;

  const name =
    product?.translations_map?.es?.name ??
    product?.translations_map?.en?.name ??
    sku;

  const specs = (product?.specs_jsonb ?? {}) as Record<string, string | null | undefined>;

  const qualityTone =
    product?.data_quality === "complete"
      ? "success"
      : product?.data_quality === "blocked"
        ? "danger"
        : "warning";

  const qualityLabel =
    product?.data_quality === "complete"
      ? "Calidad completa"
      : product?.data_quality === "blocked"
        ? "Bloqueado CG"
        : "Pendiente CG";

  if (isLoading) {
    return (
      <div className="flex w-[280px] shrink-0 flex-col gap-3 self-start rounded-lg border bg-mt-surface p-3.5" style={{ borderColor: MT.border }}>
        <MtSkeleton width="100%" height={160} />
        <MtSkeleton width="60%" height={16} />
        <MtSkeleton width="100%" height={80} />
      </div>
    );
  }

  return (
    <div
      className="mt-card-lift flex w-[280px] shrink-0 flex-col self-start overflow-hidden rounded-lg border bg-mt-surface"
      style={{ borderColor: MT.border }}
    >
      {/* Foto MT */}
      <div
        className="relative flex h-[160px] w-full items-center justify-center border-b"
        style={{ background: MT.surface3, borderColor: MT.border }}
      >
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={name}
            fill
            className="object-contain p-3"
            sizes="280px"
          />
        ) : (
          <span className="mt-mono text-[10px] uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
            sin foto
          </span>
        )}
        <span
          className="absolute left-2 top-2 mt-mono rounded-[3px] border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.6px]"
          style={{ background: MT.brandSoft, borderColor: MT.brandBorder, color: MT.brand }}
        >
          MT
        </span>
      </div>

      <div className="flex flex-col gap-2.5 p-3.5">
        {/* SKU + nombre */}
        <div>
          <div className="mt-mono text-[11px] font-semibold" style={{ color: MT.ink }}>
            {sku}
          </div>
          <div className="mt-0.5 text-[12px] font-medium leading-[1.3]" style={{ color: MT.ink2 }}>
            {name}
          </div>
        </div>

        {/* Pills */}
        <div className="flex flex-wrap gap-1">
          {product?.series_detail?.tier_id && (
            <Pill tone="brand" mono>
              Tier {product.series_detail.tier_id.slice(0, 4)}
            </Pill>
          )}
          <Pill tone={qualityTone}>{qualityLabel}</Pill>
        </div>

        {/* Divider */}
        <div className="h-px w-full" style={{ background: MT.border }} />

        {/* Specs MT */}
        <div className="flex flex-col">
          <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.6px]" style={{ color: MT.ink4 }}>
            Ficha técnica
          </div>
          <SpecRow label="Material" value={String(specs?.material ?? "—")} />
          <SpecRow label="Norma" value={String(specs?.norma ?? "—")} />
          <SpecRow label="Tipo" value={String(specs?.valve_type ?? specs?.type ?? "—")} />
          <SpecRow label="PN" value={String(specs?.pn ?? "—")} />
          <SpecRow label="Rosca" value={String(specs?.thread ?? "—")} />
        </div>

        {/* Divider */}
        <div className="h-px w-full" style={{ background: MT.border }} />

        {/* Links */}
        <div className="flex gap-1.5">
          <MtButton size="sm" className="flex-1 justify-center" asChild>
            <Link href={`/catalogo/${sku}`}>
              <FileText className="size-3.5" />
              Ficha
            </Link>
          </MtButton>
          <MtButton size="sm" className="flex-1 justify-center" asChild>
            <Link href={`/catalogo/${sku}/audit`}>
              <History className="size-3.5" />
              Histórico
            </Link>
          </MtButton>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Integrar `MtProductPanel` en page.tsx**

En `page.tsx`, importar el componente:
```tsx
import { MtProductPanel } from "./_components/mt-product-panel";
```

En el bloque `{/* Body */}`, reemplazar el bloque `{/* Left panel — SKU info */}` completo por:
```tsx
{queue.length > 0 ? (
  <MtProductPanel sku={sku} />
) : (
  <div
    className="mt-card-lift flex w-[280px] shrink-0 items-center justify-center rounded-lg border bg-mt-surface py-12"
    style={{ borderColor: MT.border, color: MT.ink4 }}
  >
    <span className="text-[12px]">Sin SKU seleccionado</span>
  </div>
)}
```

Eliminar el import de `useProduct` directo y el componente `ProductPills` en `page.tsx` (ahora encapsulado en `MtProductPanel`).

- [ ] **Step 3: Verificar en browser**

```powershell
docker restart mt-frontend
```

Abrir `http://localhost:8080/catalogo/validacion`. Verificar:
- Panel izquierdo muestra foto del producto MT (o "sin foto" si no tiene imagen)
- Specs del producto MT visibles (material, norma, tipo, PN, rosca)
- Mismo orden de specs que en las CandidateCards → comparación visual directa
- Pills de tier y calidad presentes

- [ ] **Step 4: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/_components/mt-product-panel.tsx
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): panel MT con foto, specs y pills — split-view comparación directa"
```

---

## Task 4: SkuQueuePanel — cola colapsable

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/validacion/_components/sku-queue-panel.tsx`
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

Panel colapsable con lista de SKUs pendientes. Al seleccionar uno, el panel se colapsa para dar espacio.

- [ ] **Step 1: Crear `_components/sku-queue-panel.tsx`**

```tsx
"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { MT } from "@/components/mt/tokens";

interface SkuQueueEntry {
  sku: string;
  candidateCount: number;
  bestScore: number | null;
}

interface SkuQueuePanelProps {
  entries: SkuQueueEntry[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  collapsed: boolean;
  onToggle: () => void;
}

function ScoreDot({ score }: { score: number | null }) {
  if (score === null) return <span className="size-2 rounded-full" style={{ background: MT.border }} />;
  const color = score >= 0.7 ? MT.success : score >= 0.4 ? MT.warning : MT.danger;
  return <span className="size-2 rounded-full" style={{ background: color }} />;
}

export function SkuQueuePanel({
  entries,
  selectedIndex,
  onSelect,
  collapsed,
  onToggle,
}: SkuQueuePanelProps) {
  const selectedRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (collapsed) {
    return (
      <div className="flex h-full items-start pt-1">
        <button
          type="button"
          onClick={onToggle}
          className="flex h-8 w-6 cursor-pointer items-center justify-center rounded-r-md border border-l-0 hover:bg-mt-surface-2"
          style={{ borderColor: MT.border, background: MT.surface, color: MT.ink3 }}
          title="Mostrar cola de SKUs"
        >
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex w-[220px] shrink-0 flex-col self-stretch overflow-hidden rounded-lg border bg-mt-surface"
      style={{ borderColor: MT.border }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-3 py-2"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <span className="mt-mono text-[10.5px] font-semibold uppercase tracking-[0.6px]" style={{ color: MT.ink4 }}>
          Cola · {entries.length} SKUs
        </span>
        <button
          type="button"
          onClick={onToggle}
          className="flex size-5 cursor-pointer items-center justify-center rounded hover:bg-mt-surface-3"
          style={{ color: MT.ink4 }}
          title="Colapsar cola"
        >
          <ChevronLeft className="size-3.5" />
        </button>
      </div>

      {/* Lista */}
      <div className="flex-1 overflow-y-auto">
        {entries.map((entry, idx) => {
          const isSelected = idx === selectedIndex;
          return (
            <button
              key={entry.sku}
              ref={isSelected ? selectedRef : undefined}
              type="button"
              onClick={() => {
                onSelect(idx);
                onToggle(); // colapsa al seleccionar
              }}
              className="flex w-full cursor-pointer items-center gap-2 border-b px-3 py-2 text-left hover:bg-mt-surface-2"
              style={{
                borderColor: MT.border,
                background: isSelected ? MT.brandSoft : undefined,
              }}
            >
              <ScoreDot score={entry.bestScore} />
              <div className="min-w-0 flex-1">
                <div
                  className="mt-mono truncate text-[11.5px] font-semibold"
                  style={{ color: isSelected ? MT.brand : MT.ink }}
                >
                  {entry.sku}
                </div>
                <div className="text-[10px]" style={{ color: MT.ink4 }}>
                  {entry.candidateCount} candidato{entry.candidateCount !== 1 ? "s" : ""}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Calcular `entries` a partir de datos existentes en page.tsx**

En `page.tsx`, el hook `usePendingSkuQueue()` devuelve solo los SKUs. Para calcular `candidateCount` y `bestScore` por SKU, agregar un hook secundario que obtiene todos los candidatos pendientes:

```tsx
// Dentro del componente ValidacionMatchesPage, después de usePendingSkuQueue():
const { data: allPendingData } = useQuery<{ sku: string; count: number; best: number }[]>({
  queryKey: ["matches", "sku-queue-stats"],
  queryFn: async () => {
    const res = await matchesApi.list({ status: "pending", limit: 200, include_total: false });
    const map = new Map<string, { count: number; best: number }>();
    for (const c of res.items) {
      const prev = map.get(c.product_sku);
      map.set(c.product_sku, {
        count: (prev?.count ?? 0) + 1,
        best: Math.max(prev?.best ?? 0, c.score),
      });
    }
    return Array.from(map.entries()).map(([sku, v]) => ({ sku, ...v }));
  },
  staleTime: 60_000,
});

const queueEntries = React.useMemo(
  () =>
    queue.map((sku) => {
      const stats = allPendingData?.find((s) => s.sku === sku);
      return {
        sku,
        candidateCount: stats?.count ?? 0,
        bestScore: stats?.best ?? null,
      };
    }),
  [queue, allPendingData],
);
```

- [ ] **Step 3: Añadir estado `queueCollapsed` y renderizar `SkuQueuePanel`**

```tsx
// Estado
const [queueCollapsed, setQueueCollapsed] = React.useState(false);

// Import
import { SkuQueuePanel } from "./_components/sku-queue-panel";
```

En el bloque `{/* Body */}`, antes del panel MT, insertar:
```tsx
<SkuQueuePanel
  entries={queueEntries}
  selectedIndex={clampedIndex}
  onSelect={setSkuIndex}
  collapsed={queueCollapsed}
  onToggle={() => setQueueCollapsed((v) => !v)}
/>
```

- [ ] **Step 4: Verificar en browser**

```powershell
docker restart mt-frontend
```

Abrir `http://localhost:8080/catalogo/validacion`. Verificar:
- Panel izquierdo muestra lista de SKUs pendientes con punto de color (verde/amarillo/rojo según score)
- Click en un SKU lo selecciona y colapsa el panel
- Botón chevron expande/colapsa el panel
- Al colapsar, el layout usa el espacio extra para MT panel y candidatos

- [ ] **Step 5: Commit**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/_components/sku-queue-panel.tsx
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): cola de SKUs colapsable con contadores y score dots"
```

---

## Task 5: Limpieza y ajuste del layout final

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx`

Ajustes finales del layout body, tooltip en SKU del bottom nav, y eliminación de código muerto.

- [ ] **Step 1: Ajustar el layout body a 3 columnas fluidas**

En el bloque `{/* Body */}`, cambiar el className del contenedor:

```tsx
// ANTES:
<div className="flex items-start gap-[18px] px-6 pb-20 pt-5">

// DESPUÉS:
<div className="flex items-start gap-3 px-4 pb-20 pt-4">
```

El SkuQueuePanel ya tiene `w-[220px]`, MtProductPanel tiene `w-[280px]`, y el panel de candidatos tiene `flex-1`. El gap reducido aprovecha mejor el espacio.

- [ ] **Step 2: Agregar tooltip al SKU en el bottom nav (P1)**

En el bottom nav, reemplazar el bloque del SKU actual:
```tsx
// ANTES:
<span className="mt-mono text-[14px] font-semibold" style={{ color: MT.ink }}>
  {sku}
</span>

// DESPUÉS:
<span
  className="mt-mono cursor-pointer text-[14px] font-semibold hover:underline"
  style={{ color: MT.ink }}
  title={`Copiar SKU: ${sku}`}
  onClick={() => {
    if (sku !== "—") void navigator.clipboard.writeText(sku);
  }}
>
  {sku}
</span>
```

- [ ] **Step 3: Eliminar el panel de candidatos header "Stubs" restante**

En el panel de candidatos (el `mt-card-lift` con `min-w-0 flex-1`), simplificar el header del panel:

```tsx
// ANTES:
<div className="flex items-center justify-between border-b px-4 py-3" style={{ background: MT.surface2, borderColor: MT.border }}>
  <div>
    <div className="text-[13.5px] font-semibold" style={{ color: MT.ink }}>
      Candidatos · {items.length} encontrados
    </div>
    <div className="mt-0.5 text-[11px]" style={{ color: MT.ink3 }}>
      Ordenados por score descendente · Stubs Sprint 3 (scraper Amazon real en S4)
    </div>
  </div>
</div>

// DESPUÉS:
<div
  className="flex items-center justify-between border-b px-4 py-2.5"
  style={{ background: MT.surface2, borderColor: MT.border }}
>
  <span className="text-[13px] font-semibold" style={{ color: MT.ink }}>
    Candidatos Amazon UAE
  </span>
  <span className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
    {items.length} resultado{items.length !== 1 ? "s" : ""}
  </span>
</div>
```

- [ ] **Step 4: Verificación final completa**

```powershell
docker restart mt-frontend
```

Abrir `http://localhost:8080/catalogo/validacion`. Checklist visual:

- [ ] Header ocupa ~36px (barra delgada, no gradiente)
- [ ] Cola de SKUs colapsable a la izquierda con dots de score
- [ ] Panel MT con foto + nombre + specs (mismo orden que candidatos)
- [ ] Candidatos como cards horizontales (no tabla)
- [ ] Tabs con contadores `Pendientes (N)`
- [ ] SKU en bottom nav es clickeable (copia al portapapeles)
- [ ] No hay texto "Stubs Sprint 3" en ninguna parte
- [ ] Bottom nav prev/next funciona
- [ ] Teclado ← → navega entre SKUs

- [ ] **Step 5: Commit final**

```bash
git add mt-pricing-frontend/app/(app)/catalogo/validacion/page.tsx
git commit -m "feat(validacion): layout final 3 columnas, SKU tooltip, limpieza de código muerto"
```

---

## Notas de implementación

**`product.specs_jsonb`**: Si el backend no expone `specs_jsonb` en el endpoint `GET /products/{id}`, usar los campos técnicos que sí existan en `Product` (verificar en runtime). Como fallback, mostrar "—" en todos los spec rows del panel MT.

**Imágenes Amazon**: El scraper actualmente no trae URLs de imagen. El placeholder "foto" en `CandidateCard` es intencional — reemplazar por `<Image>` real cuando el scraper lo soporte (campo `image_url` en `MatchCandidate`).

**ScorePill `size="lg"`**: Verificar que `ScorePill` acepta prop `size` — según `primitives.tsx` sí lo hace. Si falla, usar `size="md"` como fallback.

**Fase 2 (plan separado)**: Acción "Ninguno aplica" (T8→), tabs de historial inline (C4), bulk select (T10→), cola cross-SKU por score (R1), snooze (A1) — requieren cambios de backend o mayor complejidad.
