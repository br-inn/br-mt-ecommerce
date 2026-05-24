"use client";

import * as React from "react";
import { ChevronDown, ChevronRight as ChevronRightIcon, Search } from "lucide-react";

import { MT } from "@/components/mt/tokens";
import { useFacets, type FacetsFilters } from "@/lib/hooks/products/use-facets";
import type { FacetBucket, FacetsResponse } from "@/lib/api/endpoints/facets";

interface FacetSidebarProps {
  filters: FacetsFilters;
  setFilter: (key: keyof FacetsFilters, value: string | boolean | null) => void;
}

/**
 * Facet sidebar — Akeneo-style sections + Sally's UX recommendations §8:
 * - 28px density, absolute counts, top-6 + "ver más" expand
 * - Counts re-render as filters change (refinements non-destructive via backend)
 * - Sticky, ~280px wide, collapsible per section
 */
export function FacetSidebar({ filters, setFilter }: FacetSidebarProps) {
  const { data: facets, isLoading } = useFacets(filters);

  return (
    <aside
      className="mt-thin-scroll w-[280px] shrink-0 overflow-y-auto border-r"
      style={{
        borderColor: MT.border,
        background: MT.surface,
        height: "calc(100vh - 56px)",
        position: "sticky",
        top: 56,
      }}
    >
      <div className="flex items-center justify-between px-3 py-2 text-[11px] uppercase tracking-[0.6px]" style={{ color: MT.ink3 }}>
        <span>Filtros</span>
        {isLoading ? <span style={{ color: MT.ink4 }}>…</span> : null}
      </div>

      {/* Stage 3 (Wave 11) — taxonomy refinement facets */}
      <ListSection
        title="división"
        buckets={facets?.division ?? []}
        selected={filters.division ?? null}
        onToggle={(v) => setFilter("division", filters.division === v ? null : v)}
      />
      <ListSection
        title="serie"
        buckets={facets?.series ?? []}
        selected={filters.series_id ?? null}
        onToggle={(v) => setFilter("series_id", filters.series_id === v ? null : v)}
        searchable
      />
      <ListSection
        title="tier"
        buckets={facets?.tier_code ?? []}
        selected={filters.tier_code ?? null}
        onToggle={(v) => setFilter("tier_code", filters.tier_code === v ? null : v)}
      />
      <ListSection
        title="material (curado)"
        buckets={facets?.material_curated ?? []}
        selected={filters.material_id ?? null}
        onToggle={(v) => setFilter("material_id", filters.material_id === v ? null : v)}
      />

      <ListSection
        title="family"
        buckets={facets?.family ?? []}
        selected={filters.family ?? null}
        onToggle={(v) => setFilter("family", filters.family === v ? null : v)}
      />
      <ListSection
        title="material"
        buckets={facets?.material ?? []}
        selected={filters.material ?? null}
        onToggle={(v) => setFilter("material", filters.material === v ? null : v)}
      />
      <ListSection
        title="DN"
        buckets={facets?.dn ?? []}
        selected={filters.dn ?? null}
        onToggle={(v) => setFilter("dn", filters.dn === v ? null : v)}
        searchable
      />
      <ListSection
        title="PN"
        buckets={facets?.pn ?? []}
        selected={filters.pn ?? null}
        onToggle={(v) => setFilter("pn", filters.pn === v ? null : v)}
      />

      <EnumSection
        title="data_quality"
        counts={facets?.data_quality ?? {}}
        selected={filters.data_quality ?? null}
        onToggle={(v) =>
          setFilter("data_quality", filters.data_quality === v ? null : v)
        }
      />
      <EnumSection
        title="imagen"
        labels={{ with: "con foto", without: "sin foto" }}
        counts={facets?.has_image ?? {}}
        selected={
          filters.has_image === true ? "with" : filters.has_image === false ? "without" : null
        }
        onToggle={(v) =>
          setFilter(
            "has_image",
            v === "with" ? (filters.has_image === true ? null : true) : (filters.has_image === false ? null : false),
          )
        }
      />
      <EnumSection
        title="activo"
        labels={{ True: "sí", False: "no" }}
        counts={facets?.active ?? {}}
        selected={filters.active === true ? "True" : filters.active === false ? "False" : null}
        onToggle={(v) =>
          setFilter(
            "active",
            v === "True" ? (filters.active === true ? null : true) : (filters.active === false ? null : false),
          )
        }
      />

      {facets?.translation_status ? (
        <TranslationsSection facets={facets} />
      ) : null}
    </aside>
  );
}

// ────────────────────────────────────────────────────────────────────
// Sections
// ────────────────────────────────────────────────────────────────────
function SectionHeader({
  title,
  open,
  onToggle,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="mt-mono flex w-full items-center justify-between px-3 py-1.5 text-[11px] uppercase tracking-[0.6px] hover:bg-mt-surface2"
      style={{ color: MT.ink3, borderBottom: `1px solid ${MT.border}` }}
    >
      <span>{title}</span>
      {open ? <ChevronDown className="size-3" /> : <ChevronRightIcon className="size-3" />}
    </button>
  );
}

function ListSection({
  title,
  buckets,
  selected,
  onToggle,
  searchable = false,
}: {
  title: string;
  buckets: FacetBucket[];
  selected: string | null;
  onToggle: (value: string) => void;
  searchable?: boolean;
}) {
  const [open, setOpen] = React.useState(true);
  const [expanded, setExpanded] = React.useState(false);
  const [q, setQ] = React.useState("");
  const filtered = React.useMemo(
    () => (q ? buckets.filter((b) => b.value.toLowerCase().includes(q.toLowerCase())) : buckets),
    [buckets, q],
  );
  const visible = expanded ? filtered : filtered.slice(0, 6);

  return (
    <div>
      <SectionHeader title={title} open={open} onToggle={() => setOpen(!open)} />
      {open ? (
        <div className="px-2 py-1.5">
          {searchable && buckets.length > 20 ? (
            <div className="relative mb-1.5">
              <Search
                className="absolute left-2 top-1/2 size-3 -translate-y-1/2"
                style={{ color: MT.ink4 }}
              />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="filtrar…"
                className="w-full rounded-sm border bg-transparent py-1 pl-6 pr-2 text-[11.5px] outline-none focus-visible:ring-1 focus-visible:ring-mt-brand"
                style={{ borderColor: MT.border, color: MT.ink }}
              />
            </div>
          ) : null}
          <ul className="space-y-0.5">
            {visible.map((b) => (
              <li key={b.value}>
                <FacetRow
                  label={b.value}
                  count={b.count}
                  selected={selected === b.value}
                  onToggle={() => onToggle(b.value)}
                />
              </li>
            ))}
          </ul>
          {!expanded && filtered.length > 6 ? (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="mt-1 w-full px-2 py-0.5 text-left text-[11px] hover:underline"
              style={{ color: MT.ink3 }}
            >
              ver {filtered.length - 6} más ▾
            </button>
          ) : null}
          {expanded && filtered.length > 6 ? (
            <button
              type="button"
              onClick={() => setExpanded(false)}
              className="mt-1 w-full px-2 py-0.5 text-left text-[11px] hover:underline"
              style={{ color: MT.ink3 }}
            >
              colapsar ▴
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function EnumSection({
  title,
  counts,
  selected,
  onToggle,
  labels,
}: {
  title: string;
  counts: Record<string, number>;
  selected: string | null;
  onToggle: (value: string) => void;
  labels?: Record<string, string>;
}) {
  const [open, setOpen] = React.useState(true);
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  return (
    <div>
      <SectionHeader title={title} open={open} onToggle={() => setOpen(!open)} />
      {open ? (
        <ul className="space-y-0.5 px-2 py-1.5">
          {entries.map(([k, v]) => (
            <li key={k}>
              <FacetRow
                label={labels?.[k] ?? k}
                count={v}
                selected={selected === k}
                onToggle={() => onToggle(k)}
              />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function TranslationsSection({ facets }: { facets: FacetsResponse }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <SectionHeader title="traducción" open={open} onToggle={() => setOpen(!open)} />
      {open ? (
        <div className="space-y-2 px-2 py-1.5">
          {(["es", "ar"] as const).map((lang) => {
            const t = facets.translation_status[lang];
            if (!t) return null;
            return (
              <div key={lang}>
                <div className="mt-mono mb-0.5 text-[10px] uppercase" style={{ color: MT.ink4 }}>
                  {lang}
                </div>
                <ul className="space-y-0.5">
                  {(["approved", "pending", "draft", "missing"] as const).map((status) => (
                    <li key={status}>
                      <FacetRow label={status} count={t[status] ?? 0} selected={false} onToggle={() => {}} disabled />
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function FacetRow({
  label,
  count,
  selected,
  onToggle,
  disabled = false,
}: {
  label: string;
  count: number;
  selected: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled || count === 0}
      className="flex w-full items-center justify-between rounded-sm px-2 py-0.5 text-[12px] hover:bg-mt-surface2 disabled:cursor-not-allowed"
      style={{
        color: count === 0 ? MT.ink4 : selected ? MT.brand : MT.ink,
        background: selected ? `color-mix(in srgb, ${MT.brand} 12%, transparent)` : undefined,
        textDecoration: count === 0 ? "line-through" : undefined,
      }}
    >
      <span className="truncate">{label}</span>
      <span
        className="mt-mono ml-2 shrink-0 tabular-nums text-[11px]"
        style={{ color: MT.ink4 }}
      >
        {count.toLocaleString()}
      </span>
    </button>
  );
}
