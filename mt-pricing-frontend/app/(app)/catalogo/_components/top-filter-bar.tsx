"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Search, X } from "lucide-react";

import { Kbd } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";
import { materialsApi } from "@/lib/api/endpoints/materials";
import { seriesApi } from "@/lib/api/endpoints/series";
import { seriesTiersApi, type SeriesTier } from "@/lib/api/endpoints/series-tiers";
import { taxonomyApi } from "@/lib/api/endpoints/taxonomy";

const DN_FALLBACK = [
  "8", "10", "15", "20", "25", "32", "40", "50",
  "65", "80", "100", "125", "150", "200", "250", "300",
] as const;
const PN_FALLBACK = ["6", "10", "16", "25", "40", "63", "100"] as const;

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
 * UX:
 * - Línea principal (siempre visible): los filtros más usados — Búsqueda,
 *   Familia, Serie, Tier, Material — y botones [Limpiar] · [Más filtros ▼].
 * - Línea avanzada (colapsable, hidden por defecto): Subfamilia, Tipo,
 *   DN, PN, Calidad, Traducción, Activo.
 *
 * Origen de las opciones: el **registry** completo (taxonomy tree,
 * series list, tiers list, materials list) — no facets. Los `counts` de
 * facets se INYECTAN cuando están disponibles para cada opción del
 * registry. Esto evita que el dropdown se vea "vacío" cuando facets aún
 * no cargó o cuando el filtro actual deja una dimensión sin matches.
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
  const [advancedOpen, setAdvancedOpen] = React.useState(false);

  // ---- Registries (source of truth para opciones disponibles) ------------
  const taxonomyQ = useQuery({
    queryKey: ["taxonomy", "tree", "list-bar"],
    queryFn: () => taxonomyApi.tree(),
    staleTime: 5 * 60_000,
  });
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

  // ---- Lookup maps + cascada ----------------------------------------------
  const familyMaps = React.useMemo(() => {
    const familyName: Record<string, string> = {};
    const subfamilyName: Record<string, string> = {};
    const typeName: Record<string, string> = {};
    const subfamiliesByFamily: Record<string, { code: string; name: string }[]> = {};
    const typesBySubfamily: Record<string, { code: string; name: string }[]> = {};
    const allFamilies: { code: string; name: string }[] = [];
    const allSubfamilies: { code: string; name: string; family_code: string }[] = [];
    const allTypes: { code: string; name: string; subfamily_code: string }[] = [];
    for (const f of taxonomyQ.data?.families ?? []) {
      familyName[f.code] = f.name;
      subfamiliesByFamily[f.code] = [];
      allFamilies.push({ code: f.code, name: f.name });
      for (const sf of f.subfamilies) {
        subfamilyName[sf.code] = sf.name;
        subfamiliesByFamily[f.code]!.push({ code: sf.code, name: sf.name });
        allSubfamilies.push({ code: sf.code, name: sf.name, family_code: f.code });
        typesBySubfamily[sf.code] = [];
        for (const t of sf.types) {
          typeName[t.code] = t.name;
          typesBySubfamily[sf.code]!.push({ code: t.code, name: t.name });
          allTypes.push({ code: t.code, name: t.name, subfamily_code: sf.code });
        }
      }
    }
    return {
      familyName,
      subfamilyName,
      typeName,
      subfamiliesByFamily,
      typesBySubfamily,
      allFamilies,
      allSubfamilies,
      allTypes,
    };
  }, [taxonomyQ.data]);

  // ---- Count injection helpers --------------------------------------------
  // Build {value → count} maps from facet buckets so we can decorate registry
  // options with their refinement counts. If a registry option has 0 matches
  // it still shows up but with " (0)" — the user sees it's a valid option.
  const countMap = (buckets: { value: string; count: number }[] | undefined) => {
    const map: Record<string, number> = {};
    for (const b of buckets ?? []) map[b.value] = b.count;
    return map;
  };
  const familyCounts = countMap(facets?.family);
  const subfamilyCounts = countMap(facets?.subfamily);
  const typeCounts = countMap(facets?.type);
  const seriesCounts = countMap(facets?.series);
  const tierCounts = countMap(facets?.tier_code);
  const materialCounts = countMap(facets?.material_curated);
  const dnCounts = countMap(facets?.dn);
  const pnCounts = countMap(facets?.pn);

  // ---- Cascading subsets ---------------------------------------------------
  const subfamilyChoices = React.useMemo(() => {
    if (filters.family && familyMaps.subfamiliesByFamily[filters.family]) {
      return familyMaps.subfamiliesByFamily[filters.family]!;
    }
    return familyMaps.allSubfamilies;
  }, [filters.family, familyMaps]);
  const typeChoices = React.useMemo(() => {
    if (filters.subfamily && familyMaps.typesBySubfamily[filters.subfamily]) {
      return familyMaps.typesBySubfamily[filters.subfamily]!;
    }
    return familyMaps.allTypes;
  }, [filters.subfamily, familyMaps]);

  // Ordering: by count desc when present, else by name asc.
  function sortByCount<T extends { code: string; name: string }>(
    items: T[],
    counts: Record<string, number>,
  ): T[] {
    return [...items].sort((a, b) => {
      const ca = counts[a.code] ?? -1;
      const cb = counts[b.code] ?? -1;
      if (ca !== cb) return cb - ca;
      return a.name.localeCompare(b.name);
    });
  }

  return (
    <div
      className="flex flex-col gap-1.5 border-b bg-mt-surface px-6 py-2"
      style={{ borderColor: MT.border }}
    >
      {/* ─── LÍNEA PRINCIPAL (siempre visible) ───────────────────────────── */}
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

        <FilterSelect
          label="Familia"
          value={filters.family ?? ""}
          onChange={(v) => {
            setFilter("family", v || null);
            if (filters.subfamily) setFilter("subfamily", null);
            if (filters.type) setFilter("type", null);
          }}
          options={sortByCount(familyMaps.allFamilies, familyCounts).map((f) => ({
            value: f.code,
            label: f.name,
            count: familyCounts[f.code],
          }))}
        />

        <FilterSelect
          label="Serie"
          value={filters.series_id ?? ""}
          onChange={(v) => setFilter("series_id", v || null)}
          options={(seriesQ.data ?? [])
            .map((s) => ({
              value: s.id,
              label: s.name_en,
              count: seriesCounts[s.id],
            }))
            .sort((a, b) => (b.count ?? -1) - (a.count ?? -1))}
        />

        <FilterSelect
          label="Tier"
          value={filters.tier_code ?? ""}
          onChange={(v) => setFilter("tier_code", v || null)}
          options={(tiersQ.data ?? [])
            .filter((t) => t.code !== "n_a")
            .sort((a, b) => a.rank - b.rank)
            .map((t) => ({
              value: t.code,
              label: t.name,
              count: tierCounts[t.code],
            }))}
          renderDot={(opt) =>
            (tiersQ.data ?? []).find((t: SeriesTier) => t.code === opt.value)
              ?.display_color ?? null
          }
        />

        <FilterSelect
          label="Material"
          value={filters.material_id ?? ""}
          onChange={(v) => setFilter("material_id", v || null)}
          options={(materialsQ.data ?? [])
            .map((m) => ({
              value: m.id,
              label: m.name,
              count: materialCounts[m.id],
            }))
            .sort((a, b) => (b.count ?? -1) - (a.count ?? -1))}
        />

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

        <button
          type="button"
          onClick={() => setAdvancedOpen((v) => !v)}
          className="flex h-[30px] items-center gap-1 rounded-md border px-2.5 text-[11.5px] transition-colors hover:bg-mt-surface2"
          style={{
            borderColor: advancedOpen ? MT.brand : MT.border,
            color: advancedOpen ? MT.ink : MT.ink3,
            background: advancedOpen ? "rgba(229, 0, 76, 0.06)" : "transparent",
          }}
          aria-expanded={advancedOpen}
          aria-controls="advanced-filters"
        >
          {advancedOpen ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
          Más filtros
        </button>
      </div>

      {/* ─── LÍNEA AVANZADA (colapsable) ─────────────────────────────────── */}
      {advancedOpen ? (
        <div
          id="advanced-filters"
          className="flex flex-wrap items-center gap-2 rounded-md bg-mt-surface2 px-2 py-1.5"
        >
          <FilterGroup label="Sub-jerarquía">
            <FilterSelect
              label="Subfamilia"
              value={filters.subfamily ?? ""}
              onChange={(v) => {
                setFilter("subfamily", v || null);
                if (filters.type) setFilter("type", null);
              }}
              options={sortByCount(subfamilyChoices, subfamilyCounts).map((sf) => ({
                value: sf.code,
                label: sf.name,
                count: subfamilyCounts[sf.code],
              }))}
            />
            <FilterSelect
              label="Tipo"
              value={filters.type ?? ""}
              onChange={(v) => setFilter("type", v || null)}
              options={sortByCount(typeChoices, typeCounts).map((t) => ({
                value: t.code,
                label: t.name,
                count: typeCounts[t.code],
              }))}
            />
          </FilterGroup>

          <FilterGroup label="Dimensiones">
            <FilterSelect
              label="DN"
              value={filters.dn ?? ""}
              onChange={(v) => setFilter("dn", v || null)}
              options={
                (facets?.dn?.length ?? 0) > 0
                  ? (facets!.dn as { value: string; count: number }[]).map((b) => ({
                      value: b.value,
                      label: b.value,
                      count: b.count,
                    }))
                  : DN_FALLBACK.map((v) => ({
                      value: v,
                      label: v,
                      count: dnCounts[v],
                    }))
              }
            />
            <FilterSelect
              label="PN"
              value={filters.pn ?? ""}
              onChange={(v) => setFilter("pn", v || null)}
              options={
                (facets?.pn?.length ?? 0) > 0
                  ? (facets!.pn as { value: string; count: number }[]).map((b) => ({
                      value: b.value,
                      label: b.value,
                      count: b.count,
                    }))
                  : PN_FALLBACK.map((v) => ({
                      value: v,
                      label: v,
                      count: pnCounts[v],
                    }))
              }
            />
          </FilterGroup>

          <FilterGroup label="Estado">
            <FilterSelect
              label="Calidad"
              value={filters.data_quality ?? ""}
              onChange={(v) => setFilter("data_quality", v || null)}
              options={["complete", "partial", "blocked"].map((v) => ({
                value: v,
                label: v,
                count: facets?.data_quality?.[v],
              }))}
            />
            <FilterSelect
              label="Traducción"
              value={filters.translation_status ?? ""}
              onChange={(v) => setFilter("translation_status", v || null)}
              options={["pending", "draft", "approved"].map((v) => ({
                value: v,
                label: v,
              }))}
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
                { value: "true", label: "Sí", count: facets?.active?.True },
                { value: "false", label: "No", count: facets?.active?.False },
              ]}
            />
          </FilterGroup>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterGroup — etiqueta agrupadora a la izquierda de filtros relacionados.
// ---------------------------------------------------------------------------

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
// FilterSelect — pill-style native <select> with count + optional color dot.
// ---------------------------------------------------------------------------

interface Option {
  value: string;
  label: string;
  count?: number | undefined;
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
  const selectedDot =
    isActive && renderDot
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
        {options.length === 0 ? (
          <option value="" disabled>
            (sin opciones)
          </option>
        ) : null}
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
