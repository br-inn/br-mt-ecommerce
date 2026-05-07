"use client";

import * as React from "react";
import Link from "next/link";
import {
  ChevronRight,
  Download,
  Filter,
  Image as ImageIcon,
  MoreHorizontal,
  Plus,
  RefreshCcw,
  Search,
  Settings2,
  Upload,
  X,
} from "lucide-react";
import {
  parseAsString,
  parseAsStringEnum,
  parseAsBoolean,
  useQueryState,
} from "nuqs";

import {
  Kbd,
  MtButton,
  MtTd,
  MtTh,
  Pill,
  QualityBadge,
  TStatusGlyphs,
  Thumb,
  type TStatusVal,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { useProducts } from "@/lib/hooks/products/use-products";
import {
  type DataQuality,
  type ProductFilters,
  type ProductListItem,
  type TranslationStatus,
} from "@/lib/api/endpoints/products";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

const QUALITY_VALUES = ["complete", "partial", "blocked"] as const;
const TRANSLATION_VALUES = ["draft", "pending", "approved"] as const;

// US-1A-02-09-FE — filtros avanzados (dn/pn/material)
const DN_VALUES = [
  "DN8",
  "DN10",
  "DN15",
  "DN20",
  "DN25",
  "DN32",
  "DN40",
  "DN50",
  "DN65",
  "DN80",
  "DN100",
  "DN125",
  "DN150",
  "DN200",
  "DN250",
  "DN300",
] as const;
const PN_VALUES = ["PN6", "PN10", "PN16", "PN25", "PN40", "PN63", "PN100"] as const;
// Whitelist conservadora — el backend valida y devolverá [] si pasa otro valor.
const MATERIAL_VALUES = [
  "brass",
  "bronze",
  "stainless_steel",
  "carbon_steel",
  "cast_iron",
  "ductile_iron",
  "ppr",
  "pvc",
  "copper",
] as const;

function statusToVal(s: TranslationStatus | null): TStatusVal {
  if (s === "approved") return "a";
  if (s === "draft" || s === "pending") return "d";
  return "n";
}

function fmtUpdated(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const days = Math.floor(ms / (24 * 3600 * 1000));
  if (days <= 0) return "hoy";
  if (days === 1) return "hace 1 d";
  if (days < 30) return `hace ${days} d`;
  const months = Math.floor(days / 30);
  return `hace ${months} mes${months > 1 ? "es" : ""}`;
}

export default function CatalogPage() {
  const [searchInput, setSearchInput] = useQueryState("q", parseAsString.withDefault(""));
  const [family, setFamily] = useQueryState("family", parseAsString);
  const [quality, setQuality] = useQueryState(
    "quality",
    parseAsStringEnum<DataQuality>([...QUALITY_VALUES]),
  );
  const [translationStatus, setTranslationStatus] = useQueryState(
    "translation",
    parseAsStringEnum<TranslationStatus>([...TRANSLATION_VALUES]),
  );
  const [active] = useQueryState("active", parseAsBoolean.withDefault(true));
  // US-1A-02-09-FE — filtros avanzados con state en URL.
  const [dn, setDn] = useQueryState("dn", parseAsString);
  const [pn, setPn] = useQueryState("pn", parseAsString);
  const [material, setMaterial] = useQueryState("material", parseAsString);
  const [moreFiltersOpen, setMoreFiltersOpen] = React.useState(false);

  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const filters: ProductFilters = React.useMemo(
    () => ({
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
      ...(family ? { family } : {}),
      ...(quality ? { data_quality: quality } : {}),
      ...(translationStatus ? { translation_status: translationStatus } : {}),
      ...(active !== undefined ? { active } : {}),
      ...(dn ? { dn } : {}),
      ...(pn ? { pn } : {}),
      ...(material ? { material } : {}),
    }),
    [debouncedSearch, family, quality, translationStatus, active, dn, pn, material],
  );

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useProducts(filters);

  const items: ProductListItem[] = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const total = data?.pages[0]?.total ?? null;
  const activeFiltersCount = [family, quality, translationStatus, dn, pn, material].filter(
    Boolean,
  ).length;

  const clearAllFilters = React.useCallback(() => {
    void setFamily(null);
    void setQuality(null);
    void setTranslationStatus(null);
    void setDn(null);
    void setPn(null);
    void setMaterial(null);
  }, [setFamily, setQuality, setTranslationStatus, setDn, setPn, setMaterial]);

  return (
    <div className="flex h-full flex-col">
      {/* Page header */}
      <div
        className="flex items-center justify-between border-b bg-mt-surface px-6 py-3.5"
        style={{ borderColor: MT.border }}
      >
        <div className="flex items-center gap-2">
          <span className="text-[12.5px]" style={{ color: MT.ink3 }}>
            Catálogo
          </span>
          <ChevronRight className="size-3" style={{ color: MT.ink4 }} />
          <span
            className="text-[13.5px] font-semibold tracking-[-0.1px]"
            style={{ color: MT.ink }}
          >
            SKUs
          </span>
          <span className="mt-mono ml-2 text-xs" style={{ color: MT.ink4 }}>
            {total !== null ? `${total} elementos` : `${items.length} cargados`}
          </span>
        </div>
        <div className="flex gap-1.5">
          <MtButton asChild>
            <Link href="/imports">
              <Upload className="size-3.5" />
              Importer
            </Link>
          </MtButton>
          <MtButton icon={<Download className="size-3.5" />}>Exportar</MtButton>
          <MtButton tone="primary" asChild>
            <Link href="/catalogo/nuevo">
              <Plus className="size-3.5" />
              Alta SKU
            </Link>
          </MtButton>
        </div>
      </div>

      {/* Toolbar */}
      <div
        className="flex items-center gap-2.5 border-b bg-mt-surface px-6 py-2.5"
        style={{ borderColor: MT.border }}
      >
        <div
          className="flex h-[30px] w-[320px] items-center gap-2 rounded-[5px] border px-2.5 text-[12.5px]"
          style={{ background: MT.surface, borderColor: MT.border, color: MT.ink3 }}
        >
          <Search className="size-[13px]" />
          <input
            value={searchInput}
            onChange={(e) => void setSearchInput(e.target.value || null)}
            placeholder="Buscar SKU o nombre…"
            className="flex-1 bg-transparent outline-none placeholder:text-[color:var(--mt-ink-4)]"
            style={{ color: MT.ink }}
          />
          <Kbd>/</Kbd>
        </div>

        <div className="flex items-center gap-1.5">
          {family ? (
            <Pill tone="brand" dot>
              <span>family: {family}</span>
              <button
                type="button"
                onClick={() => void setFamily(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro family"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {quality ? (
            <Pill
              tone={
                quality === "blocked" ? "danger" : quality === "partial" ? "warning" : "success"
              }
              dot
            >
              <span>quality: {quality}</span>
              <button
                type="button"
                onClick={() => void setQuality(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro quality"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {translationStatus ? (
            <Pill tone="ghost">
              <span>translation: {translationStatus}</span>
              <button
                type="button"
                onClick={() => void setTranslationStatus(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro translation"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {dn ? (
            <Pill tone="ghost">
              <span>DN: {dn}</span>
              <button
                type="button"
                onClick={() => void setDn(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro DN"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {pn ? (
            <Pill tone="ghost">
              <span>PN: {pn}</span>
              <button
                type="button"
                onClick={() => void setPn(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro PN"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {material ? (
            <Pill tone="ghost">
              <span>material: {material}</span>
              <button
                type="button"
                onClick={() => void setMaterial(null)}
                className="ml-1 cursor-pointer"
                aria-label="Quitar filtro material"
              >
                <X className="size-2.5" />
              </button>
            </Pill>
          ) : null}
          {activeFiltersCount > 0 ? (
            <button
              type="button"
              onClick={clearAllFilters}
              className="ml-1 cursor-pointer text-[11.5px] underline"
              style={{ color: MT.ink3 }}
            >
              Limpiar todo
            </button>
          ) : null}
        </div>
        <span className="flex-1" />
        <MtButton
          size="sm"
          icon={<Filter className="size-3.5" />}
          onClick={() => setMoreFiltersOpen((v) => !v)}
        >
          Filtros · {activeFiltersCount}
        </MtButton>
        <MtButton size="sm" icon={<Settings2 className="size-3.5" />}>
          Columnas
        </MtButton>
      </div>

      {/* US-1A-02-09-FE — Más filtros (DN / PN / material) */}
      {moreFiltersOpen ? (
        <div
          className="grid grid-cols-3 gap-3 border-b bg-mt-surface px-6 py-3"
          style={{ borderColor: MT.border }}
        >
          <label className="flex flex-col gap-1 text-[11.5px]" style={{ color: MT.ink3 }}>
            <span className="mt-mono uppercase tracking-[0.6px]">DN</span>
            <select
              value={dn ?? ""}
              onChange={(e) => void setDn(e.target.value || null)}
              className="rounded-md border bg-transparent px-2 py-1.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand"
              style={{ borderColor: MT.border, color: MT.ink }}
            >
              <option value="">— cualquiera —</option>
              {DN_VALUES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11.5px]" style={{ color: MT.ink3 }}>
            <span className="mt-mono uppercase tracking-[0.6px]">PN</span>
            <select
              value={pn ?? ""}
              onChange={(e) => void setPn(e.target.value || null)}
              className="rounded-md border bg-transparent px-2 py-1.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand"
              style={{ borderColor: MT.border, color: MT.ink }}
            >
              <option value="">— cualquiera —</option>
              {PN_VALUES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11.5px]" style={{ color: MT.ink3 }}>
            <span className="mt-mono uppercase tracking-[0.6px]">material</span>
            <select
              value={material ?? ""}
              onChange={(e) => void setMaterial(e.target.value || null)}
              className="rounded-md border bg-transparent px-2 py-1.5 text-[13px] outline-none focus-visible:ring-2 focus-visible:ring-mt-brand"
              style={{ borderColor: MT.border, color: MT.ink }}
            >
              <option value="">— cualquiera —</option>
              {MATERIAL_VALUES.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {isError ? (
        <div className="px-6 py-3">
          <MtError
            message="No se pudieron cargar los productos."
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* Table */}
      <div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">
        <table className="mt-data-table w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 z-10">
            <tr>
              <MtTh style={{ width: 32 }}>
                <input type="checkbox" style={{ accentColor: MT.brand }} />
              </MtTh>
              <MtTh style={{ width: 110 }}>SKU</MtTh>
              <MtTh style={{ width: 40 }}>img</MtTh>
              <MtTh>name_en</MtTh>
              <MtTh>family</MtTh>
              <MtTh className="text-right">DN</MtTh>
              <MtTh className="text-right">PN</MtTh>
              <MtTh>material</MtTh>
              <MtTh>EN ES AR</MtTh>
              <MtTh>data_quality</MtTh>
              <MtTh>updated</MtTh>
              <MtTh style={{ width: 28 }}>{""}</MtTh>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 12 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    {Array.from({ length: 12 }).map((__, j) => (
                      <MtTd key={j}>
                        <MtSkeleton width={j === 3 ? 180 : 60} />
                      </MtTd>
                    ))}
                  </tr>
                ))
              : null}
            {!isLoading
              ? items.map((r, i) => {
                  const tEn: TStatusVal = "a"; // master EN considered approved baseline
                  const tEs = statusToVal(r.translation_status_es);
                  const tAr = statusToVal(r.translation_status_ar);
                  return (
                    <tr
                      key={r.id}
                      style={{
                        background: i % 2 ? MT.surface : MT.surface2,
                      }}
                    >
                      <MtTd>
                        <input type="checkbox" style={{ accentColor: MT.brand }} />
                      </MtTd>
                      <MtTd mono className="font-medium" style={{ color: MT.brand }}>
                        <Link href={`/catalogo/${r.sku}`}>{r.sku}</Link>
                      </MtTd>
                      <MtTd>
                        <Thumb />
                      </MtTd>
                      <MtTd className="font-medium" style={{ color: MT.ink }}>
                        <Link href={`/catalogo/${r.sku}`}>{r.name_en}</Link>
                      </MtTd>
                      <MtTd>
                        {r.family ? (
                          <Pill tone="ghost">{r.family}</Pill>
                        ) : (
                          <span style={{ color: MT.ink4 }}>—</span>
                        )}
                      </MtTd>
                      <MtTd mono className="text-right">
                        {r.dn ?? "—"}
                      </MtTd>
                      <MtTd mono className="text-right" style={{ color: MT.ink3 }}>
                        {r.pn ?? "—"}
                      </MtTd>
                      <MtTd mono className="text-[11.5px]" style={{ color: MT.ink3 }}>
                        {r.material ?? "—"}
                      </MtTd>
                      <MtTd>
                        <TStatusGlyphs t={{ en: tEn, es: tEs, ar: tAr }} />
                      </MtTd>
                      <MtTd>
                        <QualityBadge v={r.data_quality} />
                      </MtTd>
                      <MtTd mono className="text-[11px]" style={{ color: MT.ink3 }}>
                        {fmtUpdated(r.updated_at)}
                      </MtTd>
                      <MtTd>
                        <Link href={`/catalogo/${r.sku}`} aria-label={`Acciones ${r.sku}`}>
                          <MoreHorizontal
                            className="size-3.5 cursor-pointer"
                            style={{ color: MT.ink4 }}
                          />
                        </Link>
                      </MtTd>
                    </tr>
                  );
                })
              : null}
          </tbody>
        </table>
        {!isLoading && items.length === 0 && !isError ? (
          <MtEmpty
            title="Sin resultados"
            hint="Ajusta los filtros o limpia la búsqueda."
            icon={<ImageIcon className="size-6" strokeWidth={1.4} />}
          />
        ) : null}
      </div>

      {/* Footer */}
      <div
        className="flex items-center justify-between border-t bg-mt-surface px-6 py-2 text-[11.5px]"
        style={{ borderColor: MT.border, color: MT.ink3 }}
      >
        <span className="flex items-center gap-2">
          {total !== null
            ? `Mostrando ${items.length} de ${total}`
            : `Mostrando ${items.length}`}
          {hasNextPage ? (
            <MtButton
              size="sm"
              tone="ghost"
              onClick={() => void fetchNextPage()}
              disabled={isFetchingNextPage}
              icon={<RefreshCcw className="size-3.5" />}
            >
              {isFetchingNextPage ? "Cargando…" : "Cargar más"}
            </MtButton>
          ) : null}
        </span>
        <span className="flex items-center gap-1.5">
          <Kbd>/</Kbd> buscar · <Kbd>j</Kbd>
          <Kbd>k</Kbd> nav · <Kbd>e</Kbd> editar · <Kbd>↵</Kbd> detalle ·{" "}
          <Kbd>?</Kbd> atajos
        </span>
      </div>
    </div>
  );
}
