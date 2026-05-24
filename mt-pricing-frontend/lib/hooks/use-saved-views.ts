"use client";

import * as React from "react";
import type { FacetsFilters } from "@/lib/api/endpoints/facets";

export interface SavedView {
  id: string;
  name: string;
  filters: Partial<FacetsFilters>;
  created_at: string;
}

const STORAGE_KEY = "mt-catalog-saved-views";

function loadViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SavedView[]) : [];
  } catch {
    return [];
  }
}

function persistViews(views: SavedView[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

/**
 * Serializa los filtros de una vista como URL params de la página de catálogo.
 * Los nombres de params coinciden con los useQueryState de page.tsx.
 */
export function getShareUrl(filters: Partial<FacetsFilters>): string {
  const params = new URLSearchParams();
  if (filters.family) params.set("family", filters.family);
  if (filters.material) params.set("material", filters.material);
  if (filters.dn) params.set("dn", filters.dn);
  if (filters.pn) params.set("pn", filters.pn);
  if (filters.data_quality) params.set("quality", filters.data_quality);
  if (filters.translation_status) params.set("translation", filters.translation_status);
  if (filters.active != null) params.set("active", String(filters.active));
  if (filters.division) params.set("division", filters.division);
  if (filters.series_id) params.set("series_id", filters.series_id);
  if (filters.material_id) params.set("material_id", filters.material_id);
  if (filters.tier_code) params.set("tier_code", filters.tier_code);
  const q = params.toString();
  return `/catalogo${q ? `?${q}` : ""}`;
}

export function useSavedViews() {
  const [views, setViews] = React.useState<SavedView[]>([]);

  // Cargar al montar — solo en cliente
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setViews(loadViews());
  }, []);

  const addView = React.useCallback(
    (name: string, filters: Partial<FacetsFilters>): SavedView => {
      const newView: SavedView = {
        id: crypto.randomUUID(),
        name: name.trim(),
        filters,
        created_at: new Date().toISOString(),
      };
      setViews((prev) => {
        const updated = [...prev, newView];
        persistViews(updated);
        return updated;
      });
      return newView;
    },
    [],
  );

  const removeView = React.useCallback((id: string) => {
    setViews((prev) => {
      const updated = prev.filter((v) => v.id !== id);
      persistViews(updated);
      return updated;
    });
  }, []);

  return { views, addView, removeView };
}
