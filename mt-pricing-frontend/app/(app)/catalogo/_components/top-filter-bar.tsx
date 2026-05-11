"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";
import { ChevronDown, ChevronUp, Search, X } from "lucide-react";

import { Kbd } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";
import { taxonomyApi } from "@/lib/api/endpoints/taxonomy";
import type {
  TaxonomyNodeRead,
  TaxonomyTypeRead,
} from "@/lib/api/endpoints/taxonomy-registry";
import {
  useTaxonomyNodes,
  useTaxonomyRegistry,
} from "@/lib/hooks/use-taxonomy-registry";

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

// ---------------------------------------------------------------------------
// Resolve a localized label from `label_i18n` / `labels` with fallback chain
// (locale → es → en → slug). Same pattern usado en sidebar.tsx para mantener
// consistencia.
// ---------------------------------------------------------------------------
function resolveLabel(
  i18n: Record<string, string> | undefined,
  slug: string,
  locale: string,
): string {
  const labels = i18n ?? {};
  return (
    labels[locale] ??
    labels.es ??
    labels.en ??
    slug.charAt(0).toUpperCase() + slug.slice(1)
  );
}

// ---------------------------------------------------------------------------
// SYSTEM_FILTER_CONFIG — mapea slugs del registry a la llave del filtro en
// `FacetsFilters` y al bucket de counts en `FacetsResponse`.
//
// Tras mig 052 + actualización del endpoint /products, los filtros aceptan
// el SLUG del taxonomy_node directamente (no UUID), por lo que ya no
// necesitamos las queries legacy a seriesApi/materialsApi. El nodo del
// registry es la única fuente — su `slug` es el value y su `labels[locale]`
// es el label.
//
// Para slugs nuevos (mercados/certificaciones/aplicaciones), si no hay
// entry acá el RegistryFilter cae al default: filterKey = type.slug,
// countsBucket = type.slug.
// ---------------------------------------------------------------------------
interface SystemConfig {
  /** Key dentro de FacetsFilters al que escribimos. */
  filterKey: keyof FacetsFilters;
  /** Bucket en FacetsResponse para inyectar counts. `null` = sin counts. */
  countsBucket:
    | "family"
    | "subfamily"
    | "type"
    | "series"
    | "tier_code"
    | "material_curated"
    | "material"
    | "division"
    | "dn"
    | "pn"
    | null;
}

const SYSTEM_FILTER_CONFIG: Record<string, SystemConfig> = {
  family: { filterKey: "family", countsBucket: "family" },
  subfamily: { filterKey: "subfamily", countsBucket: "subfamily" },
  product_type: { filterKey: "type", countsBucket: "type" },
  division: { filterKey: "division", countsBucket: "division" },
  series: { filterKey: "series_id", countsBucket: "series" },
  tier: { filterKey: "tier_code", countsBucket: "tier_code" },
  material: { filterKey: "material_id", countsBucket: "material_curated" },
};

/**
 * UX:
 * - Línea principal (siempre visible): búsqueda + filtros derivados del
 *   registry polimórfico (taxonomy_types con filterable=true), ordenados por
 *   display_order y etiquetados via label_i18n[locale]. Hoy son
 *   división, serie, tier, material; cuando el admin registre `market`,
 *   `certification`, etc., aparecen automáticamente sin código.
 * - Línea avanzada (colapsable): filtros NO-registry — subfamilia, tipo,
 *   DN, PN, calidad, traducción, activo. Estos viven en columnas dedicadas
 *   de la tabla products y no pasan por el registry todavía.
 *
 * Para los 4 system slugs preservamos la cascada/dot/UUID legacy via
 * SYSTEM_FILTER_CONFIG. Para slugs nuevos, dropdown simple por default.
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
  const locale = useLocale();

  // ---- Registry (source of truth for filterable taxonomy types) -----------
  const registryQ = useTaxonomyRegistry({ filterableOnly: true });
  const registryTypes = React.useMemo(
    () =>
      [...(registryQ.data ?? [])]
        .filter((t) => t.active)
        .sort((a, b) => a.display_order - b.display_order),
    [registryQ.data],
  );

  // ---- Taxonomy tree para la cascada family→subfamily→type en la sección
  // avanzada. Cuando subfamily/product_type también vivan en el registry con
  // closure transitivo expuesto en /taxonomies/nodes, esto se puede eliminar.
  const taxonomyQ = useQuery({
    queryKey: ["taxonomy", "tree", "list-bar"],
    queryFn: () => taxonomyApi.tree(),
    staleTime: 5 * 60_000,
  });

  // Tier nodes para acceder a `attributes.display_color` y renderizar el dot.
  // Mig 050 copia series_tiers.display_color → taxonomy_nodes.attributes.
  const tierNodesQ = useTaxonomyNodes("tier");

  // Lookup maps para cascada subfamily→type (sección avanzada).
  const familyMaps = React.useMemo(() => {
    const familyName: Record<string, string> = {};
    const subfamilyName: Record<string, string> = {};
    const typeName: Record<string, string> = {};
    const subfamiliesByFamily: Record<string, { code: string; name: string }[]> = {};
    const typesBySubfamily: Record<string, { code: string; name: string }[]> = {};
    const allFamilies: { code: string; name: string }[] = [];
    const allSubfamiliesMap = new Map<string, { code: string; name: string }>();
    const allTypesMap = new Map<string, { code: string; name: string }>();
    for (const f of taxonomyQ.data?.families ?? []) {
      familyName[f.code] = f.name;
      const subBucket: { code: string; name: string }[] = [];
      const sbSeen = new Set<string>();
      for (const sf of f.subfamilies) {
        subfamilyName[sf.code] = sf.name;
        if (!sbSeen.has(sf.code)) {
          subBucket.push({ code: sf.code, name: sf.name });
          sbSeen.add(sf.code);
        }
        if (!allSubfamiliesMap.has(sf.code)) {
          allSubfamiliesMap.set(sf.code, { code: sf.code, name: sf.name });
        }
        const typeBucket: { code: string; name: string }[] = [];
        const tSeen = new Set<string>();
        for (const t of sf.types) {
          typeName[t.code] = t.name;
          if (!tSeen.has(t.code)) {
            typeBucket.push({ code: t.code, name: t.name });
            tSeen.add(t.code);
          }
          if (!allTypesMap.has(t.code)) {
            allTypesMap.set(t.code, { code: t.code, name: t.name });
          }
        }
        if (!typesBySubfamily[sf.code]) {
          typesBySubfamily[sf.code] = typeBucket;
        }
      }
      subfamiliesByFamily[f.code] = subBucket;
      allFamilies.push({ code: f.code, name: f.name });
    }
    return {
      familyName,
      subfamilyName,
      typeName,
      subfamiliesByFamily,
      typesBySubfamily,
      allFamilies,
      allSubfamilies: Array.from(allSubfamiliesMap.values()),
      allTypes: Array.from(allTypesMap.values()),
    };
  }, [taxonomyQ.data]);

  // ---- Count injection helpers --------------------------------------------
  const countMap = (buckets: { value: string; count: number }[] | undefined) => {
    const map: Record<string, number> = {};
    for (const b of buckets ?? []) map[b.value] = b.count;
    return map;
  };
  // familyCounts ya no se usa en la línea principal (el RegistryFilter lee
  // facets?.family por sí mismo via SYSTEM_FILTER_CONFIG.countsBucket).
  const subfamilyCounts = countMap(facets?.subfamily);
  const typeCounts = countMap(facets?.type);
  const dnCounts = countMap(facets?.dn);
  const pnCounts = countMap(facets?.pn);

  // Cascading subsets (sección avanzada).
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
      {/* ─── LÍNEA PRINCIPAL ─────────────────────────────────────────────── */}
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

        {/* Filtros derivados del registry polimórfico — family aparece
            automáticamente tras mig 052 (no más hardcoded). */}
        {registryQ.isLoading ? (
          <RegistryFilterSkeleton count={4} />
        ) : (
          registryTypes
            // Subfamily/product_type viven en la sección avanzada (cascada).
            .filter((t) => t.slug !== "subfamily" && t.slug !== "product_type")
            .map((type) => (
              <RegistryFilter
                key={type.id}
                type={type}
                locale={locale}
                filters={filters}
                setFilter={setFilter}
                facets={facets}
                tierNodes={tierNodesQ.data}
              />
            ))
        )}

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
// RegistryFilter — FilterSelect alimentado 100% por `useTaxonomyNodes(slug)`.
// El value del filtro es **siempre el slug del nodo** (no UUID); el backend
// (mig 052) resuelve slug→FK internamente para series_id/material_id, y los
// demás filtros ya eran code/slug-based.
// ---------------------------------------------------------------------------
interface RegistryFilterProps {
  type: TaxonomyTypeRead;
  locale: string;
  filters: FacetsFilters;
  setFilter: (key: keyof FacetsFilters, value: string | boolean | null) => void;
  facets: FacetsResponse | undefined;
  /** Tier nodes para el dot color (attributes.display_color de mig 050). */
  tierNodes: TaxonomyNodeRead[] | undefined;
}

function RegistryFilter({
  type,
  locale,
  filters,
  setFilter,
  facets,
  tierNodes,
}: RegistryFilterProps) {
  const config = SYSTEM_FILTER_CONFIG[type.slug];
  const nodesQ = useTaxonomyNodes(type.slug);

  // Filter key — para system slugs viene de config; para nuevos, slug == key.
  const filterKey = (config?.filterKey ?? (type.slug as keyof FacetsFilters)) as keyof FacetsFilters;
  const rawValue = filters[filterKey];
  const currentValue =
    typeof rawValue === "string" ? rawValue : rawValue == null ? "" : String(rawValue);

  // Counts bucket — preferimos el campo Stage 3 (division/series/tier_code/
  // material_curated). Si no aplica, usamos el slug del type como key.
  const buckets = config?.countsBucket
    ? (facets?.[config.countsBucket] as { value: string; count: number }[] | undefined)
    : (facets as unknown as Record<string, { value: string; count: number }[] | undefined>)?.[
        type.slug
      ];
  const counts: Record<string, number> = {};
  for (const b of buckets ?? []) counts[b.value] = b.count;

  // ---- Options builder --------------------------------------------------
  const options: Option[] = React.useMemo(() => {
    const nodes: TaxonomyNodeRead[] = nodesQ.data ?? [];
    return [...nodes]
      .filter((n) => n.active)
      // tier: ocultamos el legacy 'n_a' (sin nivel asignado).
      .filter((n) => !(type.slug === "tier" && n.slug === "n_a"))
      .sort((a, b) => a.display_order - b.display_order)
      .map((n) => ({
        value: n.slug,
        label: resolveLabel(n.labels, n.slug, locale),
        count: counts[n.slug],
      }));
  }, [nodesQ.data, locale, counts, type.slug]);

  // Para 'tier' renderizamos un color dot via attributes.display_color del nodo.
  const renderDot =
    type.slug === "tier"
      ? (opt: Option) => {
          const node = (tierNodes ?? []).find((n) => n.slug === opt.value);
          const color = (node?.attributes as Record<string, unknown> | undefined)?.[
            "display_color"
          ];
          return typeof color === "string" ? color : null;
        }
      : undefined;

  // Family selection cascade: limpia subfamily/type al cambiar.
  const handleChange = (v: string) => {
    setFilter(filterKey, v || null);
    if (type.slug === "family") {
      if (filters.subfamily) setFilter("subfamily", null);
      if (filters.type) setFilter("type", null);
    }
  };

  return (
    <FilterSelect
      label={resolveLabel(type.label_i18n, type.slug, locale)}
      value={currentValue}
      onChange={handleChange}
      options={options}
      {...(renderDot ? { renderDot } : {})}
    />
  );
}

// ---------------------------------------------------------------------------
// Skeleton placeholders mientras el registry carga — evita salto visual
// cuando el registry resuelve y aparecen los dropdowns.
// ---------------------------------------------------------------------------
function RegistryFilterSkeleton({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="h-[30px] w-[100px] animate-pulse rounded-md border"
          style={{ background: MT.surface, borderColor: MT.border }}
          aria-hidden
        />
      ))}
    </>
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
  const uniqueOptions = React.useMemo(() => {
    const seen = new Set<string>();
    const out: Option[] = [];
    for (const o of options) {
      if (seen.has(o.value)) continue;
      seen.add(o.value);
      out.push(o);
    }
    return out;
  }, [options]);
  const selectedDot =
    isActive && renderDot
      ? renderDot(uniqueOptions.find((o) => o.value === value) ?? { value, label })
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
        <option key="__all__" value="">
          {isActive ? "(quitar)" : "todos"}
        </option>
        {uniqueOptions.length === 0 ? (
          <option key="__none__" value="" disabled>
            (sin opciones)
          </option>
        ) : null}
        {uniqueOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
            {opt.count !== undefined ? ` (${opt.count})` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
