"use client";

import * as React from "react";
import Link from "next/link";
import {
  Download,
  Image as ImageIcon,
  MoreHorizontal,
  Plus,
  Upload,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  parseAsString,
  parseAsStringEnum,
  parseAsBoolean,
  useQueryState,
} from "nuqs";

import { materialsApi } from "@/lib/api/endpoints/materials";
import { seriesApi } from "@/lib/api/endpoints/series";
import { seriesTiersApi } from "@/lib/api/endpoints/series-tiers";

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
import { useFacets, type FacetsFilters } from "@/lib/hooks/products/use-facets";
import {
  type DataQuality,
  type ProductFilters,
  type ProductListItem,
  type TranslationStatus,
} from "@/lib/api/endpoints/products";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import { ActiveFiltersBar } from "./_components/active-filters-bar";
import { SavedViewsBar, SYSTEM_VIEWS } from "./_components/saved-views-bar";
import { Paginator } from "./_components/paginator";
import { TopFilterBar } from "./_components/top-filter-bar";

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
  const [active, setActive] = useQueryState("active", parseAsBoolean);
  // US-1A-02-09-FE — filtros avanzados con state en URL.
  const [dn, setDn] = useQueryState("dn", parseAsString);
  const [pn, setPn] = useQueryState("pn", parseAsString);
  const [material, setMaterial] = useQueryState("material", parseAsString);
  // Stage 3 (Wave 11) — taxonomy filters
  const [division, setDivision] = useQueryState("division", parseAsString);
  const [seriesId, setSeriesId] = useQueryState("series_id", parseAsString);
  const [materialId, setMaterialId] = useQueryState("material_id", parseAsString);
  const [tierCode, setTierCode] = useQueryState("tier_code", parseAsString);

  // Stage 3 lookups (cached, used to render row chips).
  const seriesListQ = useQuery({
    queryKey: ["series", "public", "list-page"],
    queryFn: () => seriesApi.listPublic({}),
    staleTime: 5 * 60_000,
  });
  const tiersListQ = useQuery({
    queryKey: ["series-tiers", "public", "list-page"],
    queryFn: () => seriesTiersApi.listPublic(),
    staleTime: 5 * 60_000,
  });
  const materialsListQ = useQuery({
    queryKey: ["materials", "public", "list-page"],
    queryFn: () => materialsApi.listPublic(),
    staleTime: 5 * 60_000,
  });

  const seriesById = React.useMemo(() => {
    const map: Record<string, { name_en: string; tier_id: string | null }> = {};
    for (const s of seriesListQ.data ?? []) {
      map[s.id] = { name_en: s.name_en, tier_id: s.tier_id };
    }
    return map;
  }, [seriesListQ.data]);
  const tierColorById = React.useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of tiersListQ.data ?? []) {
      if (t.display_color) map[t.id] = t.display_color;
    }
    return map;
  }, [tiersListQ.data]);
  const materialById = React.useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of materialsListQ.data ?? []) map[m.id] = m.name;
    return map;
  }, [materialsListQ.data]);

  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const filters: ProductFilters = React.useMemo(
    () => ({
      ...(debouncedSearch ? { search: debouncedSearch } : {}),
      ...(family ? { family } : {}),
      ...(quality ? { data_quality: quality } : {}),
      ...(translationStatus ? { translation_status: translationStatus } : {}),
      ...(active === true || active === false ? { active } : {}),
      ...(dn ? { dn } : {}),
      ...(pn ? { pn } : {}),
      ...(material ? { material } : {}),
      // Stage 3 — taxonomy
      ...(division ? { division } : {}),
      ...(seriesId ? { series_id: seriesId } : {}),
      ...(materialId ? { material_id: materialId } : {}),
      ...(tierCode ? { tier_code: tierCode } : {}),
    }),
    [
      debouncedSearch,
      family,
      quality,
      translationStatus,
      active,
      dn,
      pn,
      material,
      division,
      seriesId,
      materialId,
      tierCode,
    ],
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
  const activeFiltersCount =
    [family, quality, translationStatus, dn, pn, material].filter(Boolean).length +
    (active === null || active === undefined ? 0 : 1);

  const clearAllFilters = React.useCallback(() => {
    void setFamily(null);
    void setQuality(null);
    void setTranslationStatus(null);
    void setDn(null);
    void setPn(null);
    void setMaterial(null);
    void setActive(null);
    // Stage 3
    void setDivision(null);
    void setSeriesId(null);
    void setMaterialId(null);
    void setTierCode(null);
  }, [
    setFamily,
    setQuality,
    setTranslationStatus,
    setDn,
    setPn,
    setMaterial,
    setActive,
    setDivision,
    setSeriesId,
    setMaterialId,
    setTierCode,
  ]);

  // ---- Wave 10 facets sidebar wiring ---------------------------------------
  const facetFilters: FacetsFilters = React.useMemo(
    () => ({
      family: family ?? null,
      data_quality: quality ?? null,
      translation_status: translationStatus ?? null,
      active: active ?? null,
      dn: dn ?? null,
      pn: pn ?? null,
      material: material ?? null,
      q: debouncedSearch || null,
      // Stage 3 — taxonomy
      division: division ?? null,
      series_id: seriesId ?? null,
      material_id: materialId ?? null,
      tier_code: tierCode ?? null,
    }),
    [
      family,
      quality,
      translationStatus,
      active,
      dn,
      pn,
      material,
      debouncedSearch,
      division,
      seriesId,
      materialId,
      tierCode,
    ],
  );

  const setFacetFilter = React.useCallback(
    (key: keyof FacetsFilters, value: string | boolean | null) => {
      switch (key) {
        case "family":
          void setFamily(value as string | null);
          break;
        case "material":
          void setMaterial(value as string | null);
          break;
        case "dn":
          void setDn(value as string | null);
          break;
        case "pn":
          void setPn(value as string | null);
          break;
        case "data_quality":
          void setQuality(value as DataQuality | null);
          break;
        case "translation_status":
          void setTranslationStatus(value as TranslationStatus | null);
          break;
        case "active":
          void setActive(value as boolean | null);
          break;
        // Stage 3 (Wave 11)
        case "division":
          void setDivision(value as string | null);
          break;
        case "series_id":
          void setSeriesId(value as string | null);
          break;
        case "material_id":
          void setMaterialId(value as string | null);
          break;
        case "tier_code":
          void setTierCode(value as string | null);
          break;
      }
    },
    [
      setFamily,
      setMaterial,
      setDn,
      setPn,
      setQuality,
      setTranslationStatus,
      setActive,
      setDivision,
      setSeriesId,
      setMaterialId,
      setTierCode,
    ],
  );

  const { data: facetsData } = useFacets(facetFilters);
  const totalUnfiltered = facetsData?.total_unfiltered ?? null;
  const totalFiltered = facetsData?.total ?? total ?? null;

  const activeChips = React.useMemo(() => {
    const out: { key: string; label: string }[] = [];
    if (family) out.push({ key: "family", label: `family: ${family}` });
    if (material) out.push({ key: "material", label: `material: ${material}` });
    if (dn) out.push({ key: "dn", label: `DN: ${dn}` });
    if (pn) out.push({ key: "pn", label: `PN: ${pn}` });
    if (quality) out.push({ key: "data_quality", label: `quality: ${quality}` });
    if (translationStatus)
      out.push({ key: "translation_status", label: `traducción: ${translationStatus}` });
    if (active === true) out.push({ key: "active", label: "activos" });
    if (active === false) out.push({ key: "active", label: "inactivos" });
    return out;
  }, [family, material, dn, pn, quality, translationStatus, active]);

  const removeChip = React.useCallback(
    (key: string) => setFacetFilter(key as keyof FacetsFilters, null),
    [setFacetFilter],
  );

  const activeViewId = React.useMemo(() => {
    // Detect which system view matches the current filters (best-effort).
    const otherFilters = [family, material, dn, pn, quality, translationStatus].filter(Boolean).length;
    if (otherFilters === 0 && active === true) return "active-only";
    if (family === "unclassified" && otherFilters === 1 && active === null) return "unclassified";
    if (translationStatus === "pending" && otherFilters === 1 && active === null) return "pending-es";
    if (otherFilters === 0 && (active === null || active === undefined)) return "all";
    return "";
  }, [active, family, material, dn, pn, quality, translationStatus]);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      {/* Page header */}
      <div
        className="flex items-center justify-between border-b bg-mt-surface px-6 py-3.5"
        style={{ borderColor: MT.border }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[15px] font-semibold tracking-[-0.1px]"
            style={{ color: MT.ink }}
          >
            Productos
          </span>
          <span className="mt-mono ml-2 text-xs" style={{ color: MT.ink4 }}>
            {total !== null ? `${total} SKUs` : `${items.length} cargados`}
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

      {/* Stage 3 (Wave 11) — selector de división */}
      <div
        className="flex items-center gap-1 border-b bg-mt-surface px-6 py-2"
        style={{ borderColor: MT.border }}
      >
        <span className="mr-2 text-[12px] uppercase tracking-wide" style={{ color: MT.ink4 }}>
          División
        </span>
        {[
          { code: null, label: "Todas" },
          { code: "hidrosanitario", label: "Hidrosanitario" },
          { code: "industrial", label: "Industrial" },
        ].map((d) => {
          const selected = division === d.code;
          return (
            <button
              key={d.label}
              onClick={() => void setDivision(d.code)}
              className={`rounded-md px-2.5 py-1 text-[12.5px] transition-colors ${
                selected ? "bg-mt-accent/15 font-semibold" : "hover:bg-mt-surface-2"
              }`}
              style={{ color: selected ? MT.ink : MT.ink3 }}
            >
              {d.label}
            </button>
          );
        })}
      </div>

      {/* Wave 10 — saved views row + active filters chips */}
      <SavedViewsBar
        views={SYSTEM_VIEWS.map((v) => ({
          ...v,
          count:
            v.id === "all"
              ? totalUnfiltered ?? null
              : v.id === "unclassified"
                ? facetsData?.family.find((b) => b.value === "unclassified")?.count ?? null
                : v.id === "pending-es"
                  ? facetsData?.translation_status?.es?.pending ?? null
                  : v.id === "active-only"
                    ? facetsData?.active?.True ?? null
                    : null,
        }))}
        activeId={activeViewId}
        onSelect={(view) => {
          // Apply view filters and clear non-view filters.
          clearAllFilters();
          if (view.filters.family !== undefined) void setFamily(view.filters.family ?? null);
          if (view.filters.material !== undefined) void setMaterial(view.filters.material ?? null);
          if (view.filters.dn !== undefined) void setDn(view.filters.dn ?? null);
          if (view.filters.pn !== undefined) void setPn(view.filters.pn ?? null);
          if (view.filters.translation_status !== undefined)
            void setTranslationStatus(view.filters.translation_status ?? null);
          if (view.filters.data_quality !== undefined)
            void setQuality((view.filters.data_quality as DataQuality | undefined) ?? null);
          if (view.filters.active !== undefined) void setActive(view.filters.active ?? null);
          // Stage 3 — taxonomy
          if (view.filters.division !== undefined) void setDivision(view.filters.division ?? null);
          if (view.filters.series_id !== undefined)
            void setSeriesId(view.filters.series_id ?? null);
          if (view.filters.material_id !== undefined)
            void setMaterialId(view.filters.material_id ?? null);
          if (view.filters.tier_code !== undefined)
            void setTierCode(view.filters.tier_code ?? null);
        }}
      />
      <ActiveFiltersBar
        chips={activeChips}
        total={totalFiltered}
        totalUnfiltered={totalUnfiltered}
        onRemove={removeChip}
        onClearAll={clearAllFilters}
      />

      {/* Stage 3 (Wave 11) — barra horizontal de filtros (reemplaza la
          sidebar Wave 10 + el panel "más filtros" + las píldoras inline). */}
      <TopFilterBar
        searchInput={searchInput}
        onSearchInput={(v) => void setSearchInput(v)}
        filters={facetFilters}
        setFilter={setFacetFilter}
        facets={facetsData}
        onClearAll={clearAllFilters}
        activeFiltersCount={activeFiltersCount}
      />

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
              <MtTh>Nombre</MtTh>
              <MtTh style={{ width: 110 }}>División</MtTh>
              <MtTh>Familia</MtTh>
              <MtTh>Serie</MtTh>
              <MtTh>Material</MtTh>
              <MtTh className="text-right" style={{ width: 60 }}>
                DN
              </MtTh>
              <MtTh className="text-right" style={{ width: 60 }}>
                PN
              </MtTh>
              <MtTh style={{ width: 70 }}>Calidad</MtTh>
              <MtTh style={{ width: 70 }}>Trad</MtTh>
              <MtTh style={{ width: 90 }}>Actualizado</MtTh>
              <MtTh style={{ width: 28 }}>{""}</MtTh>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 12 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    {Array.from({ length: 14 }).map((__, j) => (
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
                      key={r.sku}
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
                        <Thumb src={r.primary_image_url} alt={r.name_en} />
                      </MtTd>
                      <MtTd className="font-medium" style={{ color: MT.ink }}>
                        <Link href={`/catalogo/${r.sku}`} className="line-clamp-2">
                          {r.name_en}
                        </Link>
                        {r.subfamily ? (
                          <span
                            className="mt-mono mt-0.5 block text-[10.5px]"
                            style={{ color: MT.ink4 }}
                          >
                            {r.subfamily}
                            {r.type ? ` · ${r.type}` : ""}
                          </span>
                        ) : null}
                      </MtTd>
                      <MtTd>
                        {r.division_codes && r.division_codes.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {r.division_codes.map((d) => (
                              <span
                                key={d}
                                className="rounded px-1.5 py-0.5 text-[10px] uppercase tracking-[0.4px]"
                                style={{
                                  background:
                                    d === "industrial"
                                      ? "rgba(229, 0, 76, 0.10)"
                                      : "rgba(10, 77, 140, 0.10)",
                                  color: d === "industrial" ? "#9c0033" : "#0a4d8c",
                                }}
                                title={`División: ${d}`}
                              >
                                {d === "industrial" ? "Indus." : "Hidro."}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: MT.ink4 }}>—</span>
                        )}
                      </MtTd>
                      <MtTd>
                        {r.family ? (
                          <Pill tone="ghost">{r.family}</Pill>
                        ) : (
                          <span style={{ color: MT.ink4 }}>—</span>
                        )}
                      </MtTd>
                      <MtTd>
                        {(() => {
                          const ser = r.series_id ? seriesById[r.series_id] : undefined;
                          if (!ser) {
                            return <span style={{ color: MT.ink4 }}>—</span>;
                          }
                          const tierColor = ser.tier_id
                            ? tierColorById[ser.tier_id]
                            : undefined;
                          return (
                            <span className="inline-flex items-center gap-1.5">
                              {tierColor ? (
                                <span
                                  className="size-2 rounded-full"
                                  style={{
                                    background: tierColor,
                                    boxShadow: `0 0 0 1px ${MT.border}`,
                                  }}
                                  aria-hidden
                                />
                              ) : null}
                              <span className="truncate" style={{ color: MT.ink2 }}>
                                {ser.name_en}
                              </span>
                            </span>
                          );
                        })()}
                      </MtTd>
                      <MtTd className="text-[11.5px]" style={{ color: MT.ink3 }}>
                        {r.material_id && materialById[r.material_id]
                          ? materialById[r.material_id]
                          : r.material ?? "—"}
                      </MtTd>
                      <MtTd mono className="text-right">
                        {r.dn ?? "—"}
                      </MtTd>
                      <MtTd mono className="text-right" style={{ color: MT.ink3 }}>
                        {r.pn ?? "—"}
                      </MtTd>
                      <MtTd>
                        <QualityBadge v={r.data_quality} />
                      </MtTd>
                      <MtTd>
                        <TStatusGlyphs t={{ en: tEn, es: tEs, ar: tAr }} />
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

      {/* Paginator (Wave 10) replaces the legacy "cargar más" footer */}
      <Paginator
        loaded={items.length}
        total={totalFiltered}
        pageSize={50}
        onPageSize={(_size) => {
          // Page size changes require refetch with new limit; useProducts
          // hook only takes filters today, so this is a no-op for now.
        }}
        hasNext={Boolean(hasNextPage)}
        onNext={() => void fetchNextPage()}
        isFetching={isFetchingNextPage}
      />

      <div
        className="flex items-center justify-end gap-1.5 border-t bg-mt-surface px-6 py-1.5 text-[11px]"
        style={{ borderColor: MT.border, color: MT.ink3 }}
      >
        <Kbd>/</Kbd> buscar · <Kbd>j</Kbd>
        <Kbd>k</Kbd> nav · <Kbd>e</Kbd> editar · <Kbd>↵</Kbd> detalle ·{" "}
        <Kbd>?</Kbd> atajos
      </div>
    </div>
  );
}
