"use client";

import * as React from "react";

import { MT } from "@/components/mt/tokens";
import type { FacetsFilters } from "@/lib/api/endpoints/facets";

interface SavedView {
  id: string;
  name: string;
  filters: Partial<FacetsFilters>;
  count?: number | null;
}

interface SavedViewsBarProps {
  views: SavedView[];
  activeId: string;
  onSelect: (view: SavedView) => void;
}

/**
 * System views (hardcoded) row + "saved by user" extension point.
 * Sally §8.6 — active view uses saturated MT.brand to differentiate from filter chips.
 */
export function SavedViewsBar({ views, activeId, onSelect }: SavedViewsBarProps) {
  return (
    <div
      className="mt-thin-scroll flex items-center gap-1 overflow-x-auto border-b px-3 py-1.5"
      style={{ borderColor: MT.border, background: MT.surface }}
    >
      <span
        className="mt-mono shrink-0 pr-1.5 text-[10.5px] uppercase tracking-[0.6px]"
        style={{ color: MT.ink4 }}
      >
        vistas
      </span>
      {views.map((view) => {
        const active = view.id === activeId;
        return (
          <button
            key={view.id}
            type="button"
            onClick={() => onSelect(view)}
            className="flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] transition-colors"
            style={{
              background: active ? MT.brand : "transparent",
              color: active ? "white" : MT.ink3,
              border: `1px solid ${active ? MT.brand : MT.border}`,
            }}
          >
            <span
              className="size-1.5 rounded-full"
              style={{ background: active ? "white" : MT.ink4 }}
            />
            <span>{view.name}</span>
            {view.count != null ? (
              <span
                className="mt-mono ml-0.5 tabular-nums text-[10.5px]"
                style={{ color: active ? "rgba(255,255,255,0.85)" : MT.ink4 }}
              >
                {view.count.toLocaleString()}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/**
 * 5 system views per Sally §8.7. Counts come from `useFacets` (caller wires).
 */
export const SYSTEM_VIEWS: SavedView[] = [
  { id: "all", name: "Todos", filters: {} },
  { id: "unclassified", name: "Sin clasificar", filters: { family: "unclassified" } },
  { id: "no-image", name: "Sin imagen", filters: { has_image: false } },
  {
    id: "pending-es",
    name: "Pendientes ES",
    filters: { translation_status: "pending", translation_lang: "es" },
  },
  { id: "active-only", name: "Sólo activos", filters: { active: true } },
];
