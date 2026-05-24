"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import {
  parseAsString,
  parseAsStringEnum,
  parseAsBoolean,
  useQueryState,
} from "nuqs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { materialsApi } from "@/lib/api/endpoints/materials";
import { seriesApi } from "@/lib/api/endpoints/series";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";

import {
  Kbd,
  MtButton,
  MtTd,
  MtTh,
  QualityBadge,
  Thumb,
} from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
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
import { getProductName } from "@/lib/utils/product-display";
import { ActiveFiltersBar } from "./_components/active-filters-bar";
import { SavedViewsBar, SYSTEM_VIEWS } from "./_components/saved-views-bar";
import { Paginator } from "./_components/paginator";
import { TopFilterBar } from "./_components/top-filter-bar";
import { useSavedViews, getShareUrl } from "@/lib/hooks/use-saved-views";
import { ProductEditDrawer } from "@/components/domain/product-edit-drawer";
import { ProductGridCard } from "./_components/product-grid-card";

const QUALITY_VALUES = ["complete", "partial", "blocked"] as const;
const TRANSLATION_VALUES = ["draft", "pending", "approved"] as const;


// ---- B1: exportar CSV -------------------------------------------------------
function exportToCsv(items: ProductListItem[], filename: string) {
  const headers = [
    "sku",
    "family",
    "subfamily",
    "type",
    "material",
    "dn",
    "pn",
    "lifecycle_status",
    "data_quality",
    "updated_at",
  ] as const;
  const rows = items.map((r) =>
    headers.map((h) => String((r as unknown as Record<string, unknown>)[h] ?? "")).join(","),
  );
  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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

function storeNavContext(skus: string[]): void {
  try {
    sessionStorage.setItem("mt-catalog-nav", JSON.stringify(skus));
  } catch {
    // ignore — sessionStorage unavailable (SSR, private mode)
  }
}

export default function CatalogPage() {
  const router = useRouter();

  // B2 — selección múltiple
  const [selectedSkus, setSelectedSkus] = React.useState<Set<string>>(new Set());

  // B3 — fila activa para navegación con teclado
  const [activeIndex, setActiveIndex] = React.useState<number | null>(null);

  // A-4 — hover state para acciones contextuales por fila
  const [hoveredSku, setHoveredSku] = React.useState<string | null>(null);

  // B3 — modal de atajos de teclado
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);

  // B4 — page size
  const [pageLimit, setPageLimit] = React.useState(25);

  // A2 — modo de visualización
  const [viewMode, setViewMode] = React.useState<"table" | "grid">("table");
  // A2 — quick edit desde tabla/galería
  const [quickEditSku, setQuickEditSku] = React.useState<string | null>(null);

  // Saved views — persistidas en localStorage
  const { views: savedUserViews, addView, removeView } = useSavedViews();

  const [searchInput, setSearchInput] = useQueryState("q", parseAsString.withDefault(""));
  const [family, setFamily] = useQueryState("family", parseAsString);
  const [subfamily, setSubfamily] = useQueryState("subfamily", parseAsString);
  const [typeFilter, setTypeFilter] = useQueryState("type", parseAsString);
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
  const materialsListQ = useQuery({
    queryKey: ["materials", "public", "list-page"],
    queryFn: () => materialsApi.listPublic(),
    staleTime: 5 * 60_000,
  });

  const seriesById = React.useMemo(() => {
    const map: Record<string, { name_en: string }> = {};
    for (const s of seriesListQ.data ?? []) {
      map[s.id] = { name_en: s.name_en };
    }
    return map;
  }, [seriesListQ.data]);
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
      ...(subfamily ? { subfamily } : {}),
      ...(typeFilter ? { type: typeFilter } : {}),
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
      // B4 — page size
      limit: pageLimit,
    }),
    [
      debouncedSearch,
      family,
      subfamily,
      typeFilter,
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
      pageLimit,
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

  // B3 — keyboard shortcuts
  React.useEffect(() => {
    function isInputFocused(): boolean {
      const el = document.activeElement;
      if (!el) return false;
      const tag = el.tagName.toLowerCase();
      return tag === "input" || tag === "textarea" || tag === "select" || (el as HTMLElement).isContentEditable;
    }

    function onKeyDown(e: KeyboardEvent) {
      // Ignore when modifier keys are held (except shift for ? which is implicit)
      if (e.ctrlKey || e.altKey || e.metaKey) return;

      // "/" — focus search input
      if (e.key === "/" && !isInputFocused()) {
        e.preventDefault();
        const searchEl = document.querySelector<HTMLInputElement>('input[type="search"], input[placeholder*="buscar" i], input[placeholder*="search" i]');
        if (searchEl) searchEl.focus();
        return;
      }

      // "?" — toggle shortcuts modal
      if (e.key === "?" && !isInputFocused()) {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
        return;
      }

      // Navigation: j/k (only when not in input)
      if (e.key === "j" && !isInputFocused()) {
        e.preventDefault();
        setActiveIndex((prev) => {
          if (items.length === 0) return null;
          if (prev === null) return 0;
          return Math.min(prev + 1, items.length - 1);
        });
        return;
      }
      if (e.key === "k" && !isInputFocused()) {
        e.preventDefault();
        setActiveIndex((prev) => {
          if (items.length === 0) return null;
          if (prev === null) return 0;
          return Math.max(prev - 1, 0);
        });
        return;
      }

      // Enter — navigate to detail
      if (e.key === "Enter" && !isInputFocused() && activeIndex !== null && items[activeIndex]) {
        e.preventDefault();
        router.push(`/catalogo/${items[activeIndex].sku}`);
        return;
      }

      // "e" — navigate to edit
      if (e.key === "e" && !isInputFocused() && activeIndex !== null && items[activeIndex]) {
        e.preventDefault();
        router.push(`/catalogo/${items[activeIndex].sku}/edit`);
        return;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [items, activeIndex, router]);
  const activeFiltersCount =
    [
      family,
      subfamily,
      typeFilter,
      quality,
      translationStatus,
      dn,
      pn,
      material,
      division,
      seriesId,
      materialId,
      tierCode,
    ].filter(Boolean).length + (active === null || active === undefined ? 0 : 1);

  const clearAllFilters = React.useCallback(() => {
    void setFamily(null);
    void setSubfamily(null);
    void setTypeFilter(null);
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
    setSubfamily,
    setTypeFilter,
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
      subfamily: subfamily ?? null,
      type: typeFilter ?? null,
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
      subfamily,
      typeFilter,
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
        case "subfamily":
          void setSubfamily(value as string | null);
          break;
        case "type":
          void setTypeFilter(value as string | null);
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
      setSubfamily,
      setTypeFilter,
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
    if (quality === "partial" && otherFilters === 1 && active === null) return "quality-review";
    if (otherFilters === 0 && (active === null || active === undefined)) return "all";
    return "";
  }, [active, family, material, dn, pn, quality, translationStatus]);

  // Callback para guardar la vista actual con el nombre indicado.
  const handleSaveCurrentView = React.useCallback(
    (name: string) => {
      addView(name, {
        family: family ?? null,
        material: material ?? null,
        dn: dn ?? null,
        pn: pn ?? null,
        data_quality: quality ?? null,
        translation_status: translationStatus ?? null,
        active: active ?? null,
        division: division ?? null,
        series_id: seriesId ?? null,
        material_id: materialId ?? null,
        tier_code: tierCode ?? null,
      });
    },
    [addView, family, material, dn, pn, quality, translationStatus, active, division, seriesId, materialId, tierCode],
  );

  // Callback para aplicar los filtros de una vista (system o user).
  const handleSelectView = React.useCallback(
    (view: { filters: Partial<import("@/lib/api/endpoints/facets").FacetsFilters> }) => {
      clearAllFilters();
      const f = view.filters;
      if (f.family !== undefined) void setFamily(f.family ?? null);
      if (f.material !== undefined) void setMaterial(f.material ?? null);
      if (f.dn !== undefined) void setDn(f.dn ?? null);
      if (f.pn !== undefined) void setPn(f.pn ?? null);
      if (f.translation_status !== undefined) void setTranslationStatus(f.translation_status ?? null);
      if (f.data_quality !== undefined) void setQuality((f.data_quality as import("@/lib/api/endpoints/products").DataQuality | undefined) ?? null);
      if (f.active !== undefined) void setActive(f.active ?? null);
      if (f.division !== undefined) void setDivision(f.division ?? null);
      if (f.series_id !== undefined) void setSeriesId(f.series_id ?? null);
      if (f.material_id !== undefined) void setMaterialId(f.material_id ?? null);
      if (f.tier_code !== undefined) void setTierCode(f.tier_code ?? null);
    },
    [
      clearAllFilters,
      setFamily,
      setMaterial,
      setDn,
      setPn,
      setTranslationStatus,
      setQuality,
      setActive,
      setDivision,
      setSeriesId,
      setMaterialId,
      setTierCode,
    ],
  );

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
              <Upload className="size-3.5" />
              Importer
            </Link>
          </MtButton>
          <MtButton
            icon={<Download className="size-3.5" />}
            onClick={() => exportToCsv(items, `productos-${Date.now()}.csv`)}
          >
            Exportar
          </MtButton>
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
        onSelect={handleSelectView}
        userViews={savedUserViews}
        onSaveCurrentView={handleSaveCurrentView}
        onDeleteView={removeView}
        onShareView={handleShareView}
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

      {/* B2 — Bulk actions toolbar */}
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
        <table className="mt-data-table w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 z-10">
            <tr>
              <MtTh style={{ width: 32 }}>
                {/* B2 — select all checkbox */}
                <SelectAllCheckbox
                  items={items}
                  selectedSkus={selectedSkus}
                  setSelectedSkus={setSelectedSkus}
                />
              </MtTh>
              <MtTh style={{ width: 48 }}>img</MtTh>
              <MtTh style={{ width: 120 }}>SKU</MtTh>
              <MtTh>Nombre</MtTh>
              <MtTh className="text-right" style={{ width: 60 }}>
                DN
              </MtTh>
              <MtTh className="text-right" style={{ width: 60 }}>
                PN
              </MtTh>
              <MtTh style={{ width: 110 }}>Estado</MtTh>
              <MtTh style={{ width: 80 }}>Calidad</MtTh>
              <MtTh style={{ width: 95 }}>Actualizado</MtTh>
              <MtTh style={{ width: 32 }}>{""}</MtTh>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 12 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    {Array.from({ length: 10 }).map((__, j) => (
                      <MtTd key={j}>
                        <MtSkeleton width={j === 3 ? 180 : 60} />
                      </MtTd>
                    ))}
                  </tr>
                ))
              : null}
            {!isLoading
              ? items.map((r, i) => {
                  const isActive = activeIndex === i;
                  const isChecked = selectedSkus.has(r.sku);
                  return (
                    <tr
                      key={r.sku}
                      onClick={() => setActiveIndex(i)}
                      onMouseEnter={() => setHoveredSku(r.sku)}
                      onMouseLeave={() => setHoveredSku(null)}
                      style={{
                        background: i % 2 ? MT.surface : MT.surface2,
                        // B3 — highlight active row with brand left border
                        boxShadow: isActive ? `inset 3px 0 0 ${MT.brand}` : undefined,
                        cursor: "default",
                      }}
                    >
                      {/* checkbox */}
                      <MtTd>
                        {/* B2 — row checkbox */}
                        <input
                          type="checkbox"
                          style={{ accentColor: MT.brand }}
                          checked={isChecked}
                          onChange={() => {
                            setSelectedSkus((prev) => {
                              const next = new Set(prev);
                              if (next.has(r.sku)) {
                                next.delete(r.sku);
                              } else {
                                next.add(r.sku);
                              }
                              return next;
                            });
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </MtTd>
                      {/* img (48px) */}
                      <MtTd>
                        {r.primary_image_url ? (
                          <img
                            src={r.primary_image_url}
                            alt=""
                            loading="lazy"
                            decoding="async"
                            className="h-10 w-10 rounded-md object-cover"
                            style={{ border: `1px solid ${MT.border}` }}
                          />
                        ) : (
                          <Thumb />
                        )}
                      </MtTd>
                      {/* SKU */}
                      <MtTd mono className="font-medium" style={{ color: MT.brand }}>
                        <Link href={`/catalogo/${r.sku}`} onClick={() => storeNavContext(items.map((i) => i.sku))}>
                          {r.sku}
                        </Link>
                      </MtTd>
                      {/* Nombre compuesto — A-1 */}
                      <MtTd className="font-medium" style={{ color: MT.ink, minWidth: 280, maxWidth: 420 }}>
                        <Link
                          href={`/catalogo/${r.sku}`}
                          className="line-clamp-1 hover:underline"
                          onClick={() => storeNavContext(items.map((i) => i.sku))}
                        >
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
                      {/* DN */}
                      <MtTd mono className="text-right">
                        {r.dn ?? "—"}
                      </MtTd>
                      {/* PN */}
                      <MtTd mono className="text-right" style={{ color: MT.ink3 }}>
                        {r.pn ?? "—"}
                      </MtTd>
                      {/* Estado */}
                      <MtTd>
                        <LifecycleStatusBadge status={r.lifecycle_status} />
                      </MtTd>
                      {/* Calidad */}
                      <MtTd>
                        <QualityBadge v={r.data_quality} />
                      </MtTd>
                      {/* Actualizado */}
                      <MtTd mono className="text-[11px]" style={{ color: MT.ink3 }}>
                        {fmtUpdated(r.updated_at)}
                      </MtTd>
                      {/* Acciones — A-4 */}
                      <MtTd>
                        <div className="flex items-center justify-end gap-1">
                          {hoveredSku === r.sku ? (
                            <>
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
                          )}
                        </div>
                      </MtTd>
                    </tr>
                  );
                })
              : null}
          </tbody>
        </table>
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
      </div>
      ) : null}

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

      {/* Paginator (Wave 10) replaces the legacy "cargar más" footer */}
      <Paginator
        loaded={items.length}
        total={totalFiltered}
        pageSize={pageLimit}
        onPageSize={setPageLimit}
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
        <button
          type="button"
          className="inline-flex items-center gap-1 hover:underline"
          onClick={() => setShortcutsOpen(true)}
        >
          <Kbd>?</Kbd> atajos
        </button>
      </div>

      {/* B3 — Modal de atajos de teclado */}
      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Atajos de teclado</DialogTitle>
          </DialogHeader>
          <table className="w-full text-[12.5px]">
            <tbody>
              {[
                { key: "/", desc: "Enfocar buscador" },
                { key: "j", desc: "Fila siguiente" },
                { key: "k", desc: "Fila anterior" },
                { key: "↵", desc: "Ver detalle del producto activo" },
                { key: "e", desc: "Editar producto activo" },
                { key: "?", desc: "Mostrar / ocultar este panel" },
              ].map(({ key, desc }) => (
                <tr key={key} className="border-b last:border-b-0" style={{ borderColor: MT.border }}>
                  <td className="py-2 pr-4">
                    <Kbd>{key}</Kbd>
                  </td>
                  <td className="py-2" style={{ color: MT.ink2 }}>
                    {desc}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---- B2 — Select All Checkbox (indeterminate support) ----------------------
function SelectAllCheckbox({
  items,
  selectedSkus,
  setSelectedSkus,
}: {
  items: ProductListItem[];
  selectedSkus: Set<string>;
  setSelectedSkus: React.Dispatch<React.SetStateAction<Set<string>>>;
}) {
  const ref = React.useRef<HTMLInputElement>(null);
  const allSelected = items.length > 0 && items.every((r) => selectedSkus.has(r.sku));
  const someSelected = !allSelected && items.some((r) => selectedSkus.has(r.sku));

  React.useEffect(() => {
    if (ref.current) {
      ref.current.indeterminate = someSelected;
    }
  }, [someSelected]);

  return (
    <input
      ref={ref}
      type="checkbox"
      style={{ accentColor: MT.brand }}
      checked={allSelected}
      onChange={() => {
        if (allSelected) {
          setSelectedSkus(new Set());
        } else {
          setSelectedSkus(new Set(items.map((r) => r.sku)));
        }
      }}
    />
  );
}
