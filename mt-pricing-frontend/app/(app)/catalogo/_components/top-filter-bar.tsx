"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X } from "lucide-react";

import { Kbd } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { divisionsApi, type Division } from "@/lib/api/endpoints/divisions";
import { type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";
import { materialsApi, type Material } from "@/lib/api/endpoints/materials";
import { seriesApi, type Series } from "@/lib/api/endpoints/series";
import { seriesTiersApi, type SeriesTier } from "@/lib/api/endpoints/series-tiers";
import { taxonomyApi } from "@/lib/api/endpoints/taxonomy";

const DN_VALUES = [
  "DN8", "DN10", "DN15", "DN20", "DN25", "DN32", "DN40", "DN50",
  "DN65", "DN80", "DN100", "DN125", "DN150", "DN200", "DN250", "DN300",
] as const;
const PN_VALUES = ["PN6", "PN10", "PN16", "PN25", "PN40", "PN63", "PN100"] as const;
const QUALITY_VALUES = ["complete", "partial", "blocked"] as const;
const TRANSLATION_VALUES = ["draft", "pending", "approved"] as const;

interface Props {
  searchInput: string;
  onSearchInput: (value: string | null) => void;
  filters: FacetsFilters;
  setFilter: (key: keyof FacetsFilters, value: string | boolean | null) => void;
  facets: FacetsResponse | undefined;
  onClearAll: () => void;
  activeFiltersCount: number;
}

/**
 * Compact horizontal filter bar — replaces the previous left-side `FacetSidebar`
 * + the inline chips/“Más filtros” panel. All Stage 3 (Wave 11) taxonomy filters
 * (división, serie, tier, material curado) plus legacy filters (family, DN, PN,
 * material TEXT, calidad, traducción, activo) live here.
 *
 * UX principles:
 * - Single horizontal row of <select> popovers, native + accesibles.
 * - Counts incrustados en cada opción usando los buckets de facets.
 * - Búsqueda principal a la izquierda, "Limpiar todo" a la derecha.
 * - El selector de división vive arriba (tabs) — aquí no se duplica.
 */
export function TopFilterBar({
  searchInput,
  onSearchInput,
  filters,
  setFilter,
  facets,
  onClearAll,
  activeFiltersCount,
}: Props) {
  const seriesQ = useQuery({
    queryKey: ["series", "public", "list-bar"],
    queryFn: () => seriesApi.listPublic({}),
    staleTime: 5 * 60_000,
  });
  const tiersQ = useQuery({
    queryKey: ["series-tiers", "public", "list-bar"],
    queryFn: () => seriesTiersApi.listPublic(),
    staleTime: 5 * 60_000,
  });
  const materialsQ = useQuery({
    queryKey: ["materials", "public", "list-bar"],
    queryFn: () => materialsApi.listPublic(),
    staleTime: 5 * 60_000,
  });
  const taxonomyQ = useQuery({
    queryKey: ["taxonomy", "tree", "list-bar"],
    queryFn: () => taxonomyApi.tree(),
    staleTime: 5 * 60_000,
  });

  // family CODE → NAME (display) + subfamilias hijas + types nietos.
  const familyMaps = React.useMemo(() => {
    const familyName: Record<string, string> = {};
    const subfamilyName: Record<string, string> = {};
    const typeName: Record<string, string> = {};
    const subfamiliesByFamily: Record<string, string[]> = {};
    const typesBySubfamily: Record<string, string[]> = {};
    for (const f of taxonomyQ.data?.families ?? []) {
      familyName[f.code] = f.name;
      subfamiliesByFamily[f.code] = [];
      for (const sf of f.subfamilies) {
        subfamilyName[sf.code] = sf.name;
        subfamiliesByFamily[f.code]!.push(sf.code);
        typesBySubfamily[sf.code] = [];
        for (const t of sf.types) {
          typeName[t.code] = t.name;
          typesBySubfamily[sf.code]!.push(t.code);
        }
      }
    }
    return { familyName, subfamilyName, typeName, subfamiliesByFamily, typesBySubfamily };
  }, [taxonomyQ.data]);

  const seriesById = React.useMemo<Record<string, Series>>(() => {
    const map: Record<string, Series> = {};
    for (const s of seriesQ.data ?? []) map[s.id] = s;
    return map;
  }, [seriesQ.data]);

  const materialsById = React.useMemo<Record<string, Material>>(() => {
    const map: Record<string, Material> = {};
    for (const m of materialsQ.data ?? []) map[m.id] = m;
    return map;
  }, [materialsQ.data]);

  const familyBuckets = facets?.family ?? [];
  const subfamilyBuckets = facets?.subfamily ?? [];
  const typeBuckets = facets?.type ?? [];
  const seriesBuckets = facets?.series ?? [];
  const tierBuckets = facets?.tier_code ?? [];
  const materialCuratedBuckets = facets?.material_curated ?? [];
  const dnBuckets = facets?.dn ?? [];
  const pnBuckets = facets?.pn ?? [];

  // Cascada: si family seleccionada → restringe subfamilias a sus hijas;
  // si subfamily seleccionada → restringe types a sus hijos.
  const subfamilyOptions = React.useMemo(() => {
    const allowed = filters.family ? familyMaps.subfamiliesByFamily[filters.family] : null;
    return subfamilyBuckets.filter((b) => !allowed || allowed.includes(b.value));
  }, [subfamilyBuckets, filters.family, familyMaps]);
  const typeOptions = React.useMemo(() => {
    const allowed = filters.subfamily
      ? familyMaps.typesBySubfamily[filters.subfamily]
      : null;
    return typeBuckets.filter((b) => !allowed || allowed.includes(b.value));
  }, [typeBuckets, filters.subfamily, familyMaps]);

  return (
    <div
      className="flex flex-col gap-1.5 border-b bg-mt-surface px-6 py-2"
      style={{ borderColor: MT.border }}
    >
      {/* Row 1 — Búsqueda + Taxonomía + Comercial */}
      <div className="flex flex-wrap items-center gap-2">
        <div
          className="flex h-[30px] min-w-[260px] flex-1 items-center gap-2 rounded-[5px] border px-2.5 text-[12.5px]"
          style={{ background: MT.surface, borderColor: MT.border, color: MT.ink3 }}
        >
          <Search className="size-[13px]" />
          <input
            value={searchInput}
            onChange={(e) => onSearchInput(e.target.value || null)}
            placeholder="Buscar SKU o nombre…"
            className="flex-1 bg-transparent outline-none placeholder:text-[color:var(--mt-ink-4)]"
            style={{ color: MT.ink }}
          />
          <Kbd>/</Kbd>
        </div>

        <FilterGroup label="Taxonomía">
          <FilterSelect
            label="Familia"
            value={filters.family ?? ""}
            onChange={(v) => {
              setFilter("family", v || null);
              // Cambio de family invalida sub/tipo seleccionados.
              if (filters.subfamily) setFilter("subfamily", null);
              if (filters.type) setFilter("type", null);
            }}
            options={familyBuckets.map((b) => ({
              value: b.value,
              label: familyMaps.familyName[b.value] ?? b.value,
              count: b.count,
            }))}
          />
          <FilterSelect
            label="Subfamilia"
            value={filters.subfamily ?? ""}
            onChange={(v) => {
              setFilter("subfamily", v || null);
              if (filters.type) setFilter("type", null);
            }}
            options={subfamilyOptions.map((b) => ({
              value: b.value,
              label: familyMaps.subfamilyName[b.value] ?? b.value,
              count: b.count,
            }))}
          />
          <FilterSelect
            label="Tipo"
            value={filters.type ?? ""}
            onChange={(v) => setFilter("type", v || null)}
            options={typeOptions.map((b) => ({
              value: b.value,
              label: familyMaps.typeName[b.value] ?? b.value,
              count: b.count,
            }))}
          />
        </FilterGroup>

        <FilterGroup label="Comercial">
          <FilterSelect
            label="Serie"
            value={filters.series_id ?? ""}
            onChange={(v) => setFilter("series_id", v || null)}
            options={seriesBuckets.map((b) => ({
              value: b.value,
              label: seriesById[b.value]?.name_en ?? b.value.slice(0, 8),
              count: b.count,
            }))}
          />
          <FilterSelect
            label="Tier"
            value={filters.tier_code ?? ""}
            onChange={(v) => setFilter("tier_code", v || null)}
            options={tierBuckets.map((b) => ({
              value: b.value,
              label: b.value,
              count: b.count,
            }))}
            renderDot={(opt) => {
              const t = (tiersQ.data ?? []).find((x: SeriesTier) => x.code === opt.value);
              return t?.display_color ?? null;
            }}
          />
        </FilterGroup>

        <span className="flex-1" />
        {activeFiltersCount > 0 ? (
          <button
            type="button"
            onClick={onClearAll}
            className="flex h-[30px] items-center gap-1 rounded-md border px-2 text-[11.5px] transition-colors hover:bg-mt-surface2"
            style={{ borderColor: MT.border, color: MT.ink3 }}
          >
            <X className="size-3" />
            Limpiar ({activeFiltersCount})
          </button>
        ) : null}
      </div>

      {/* Row 2 — Especificaciones + Estado */}
      <div className="flex flex-wrap items-center gap-2">
        <FilterGroup label="Especificaciones">
          <FilterSelect
            label="Material"
            value={filters.material_id ?? ""}
            onChange={(v) => setFilter("material_id", v || null)}
            options={materialCuratedBuckets.map((b) => ({
              value: b.value,
              label: materialsById[b.value]?.name ?? b.value.slice(0, 8),
              count: b.count,
            }))}
          />
          <FilterSelect
            label="DN"
            value={filters.dn ?? ""}
            onChange={(v) => setFilter("dn", v || null)}
            options={
              dnBuckets.length > 0
                ? dnBuckets.map((b) => ({ value: b.value, label: b.value, count: b.count }))
                : DN_VALUES.map((v) => ({ value: v, label: v }))
            }
          />
          <FilterSelect
            label="PN"
            value={filters.pn ?? ""}
            onChange={(v) => setFilter("pn", v || null)}
            options={
              pnBuckets.length > 0
                ? pnBuckets.map((b) => ({ value: b.value, label: b.value, count: b.count }))
                : PN_VALUES.map((v) => ({ value: v, label: v }))
            }
          />
        </FilterGroup>

        <FilterGroup label="Estado">
          <FilterSelect
            label="Calidad"
            value={filters.data_quality ?? ""}
            onChange={(v) => setFilter("data_quality", v || null)}
            options={QUALITY_VALUES.map((v) => ({ value: v, label: v }))}
          />
          <FilterSelect
            label="Trad."
            value={filters.translation_status ?? ""}
            onChange={(v) => setFilter("translation_status", v || null)}
            options={TRANSLATION_VALUES.map((v) => ({ value: v, label: v }))}
          />
          <FilterSelect
            label="Activo"
            value={
              filters.active === true ? "true" : filters.active === false ? "false" : ""
            }
            onChange={(v) =>
              setFilter("active", v === "true" ? true : v === "false" ? false : null)
            }
            options={[
              { value: "true", label: "sí" },
              { value: "false", label: "no" },
            ]}
          />
        </FilterGroup>
      </div>
    </div>
  );
}

// FilterGroup — etiqueta agrupadora en mayúsculas pequeñas a la izquierda de
// un cluster de filtros relacionados. Mejora el escaneo visual de la barra.
function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1">
      <span
        className="mt-mono mr-0.5 text-[10px] uppercase tracking-[0.6px]"
        style={{ color: MT.ink4 }}
      >
        {label}
      </span>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterSelect — pill-style native <select> with count + optional color dot
// ---------------------------------------------------------------------------

interface Option {
  value: string;
  label: string;
  count?: number;
}

interface FilterSelectProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  renderDot?: (opt: Option) => string | null;
}

function FilterSelect({ label, value, onChange, options, renderDot }: FilterSelectProps) {
  const isActive = value !== "";
  const selectedDot = isActive && renderDot
    ? renderDot(options.find((o) => o.value === value) ?? { value, label })
    : null;
  return (
    <label
      className="flex h-[30px] cursor-pointer items-center gap-1.5 rounded-md border bg-mt-surface px-2 text-[12px] transition-colors hover:bg-mt-surface2"
      style={{
        borderColor: isActive ? MT.brand : MT.border,
        color: isActive ? MT.ink : MT.ink3,
      }}
    >
      <span
        className="mt-mono text-[10px] uppercase tracking-[0.6px]"
        style={{ color: MT.ink4 }}
      >
        {label}
      </span>
      {selectedDot ? (
        <span
          className="size-2 rounded-full"
          style={{ background: selectedDot, boxShadow: `0 0 0 1px ${MT.border}` }}
          aria-hidden
        />
      ) : null}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer bg-transparent pr-1 text-[12.5px] outline-none"
        style={{ color: isActive ? MT.ink : MT.ink3 }}
        aria-label={label}
      >
        <option value="">{isActive ? "(quitar)" : "todos"}</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
            {opt.count !== undefined ? ` (${opt.count})` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
