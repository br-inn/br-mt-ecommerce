"use client";

import * as React from "react";

import { Link2 } from "lucide-react";

import { MT } from "@/components/mt/tokens";
import type { FacetsFilters } from "@/lib/api/endpoints/facets";
import type { SavedView as UserSavedView } from "@/lib/hooks/use-saved-views";

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
  /** Vistas guardadas por el usuario (persistidas en localStorage). */
  userViews?: UserSavedView[];
  /** Guardar los filtros actuales con el nombre dado. */
  onSaveCurrentView?: (name: string) => void;
  /** Eliminar una vista de usuario por id. */
  onDeleteView?: (id: string) => void;
  /** Compartir URL de una vista de usuario por id. */
  onShareView?: (id: string) => void;
}

/**
 * System views (hardcoded) row + "saved by user" extension point.
 * Sally §8.6 — active view uses saturated MT.brand to differentiate from filter chips.
 */
export function SavedViewsBar({
  views,
  activeId,
  onSelect,
  userViews = [],
  onSaveCurrentView,
  onDeleteView,
  onShareView,
}: SavedViewsBarProps) {
  const [showNameInput, setShowNameInput] = React.useState(false);
  const [viewName, setViewName] = React.useState("");

  function handleSave() {
    const trimmed = viewName.trim();
    if (trimmed && onSaveCurrentView) {
      onSaveCurrentView(trimmed);
    }
    setViewName("");
    setShowNameInput(false);
  }

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

      {/* System views */}
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

      {/* Separador + sección de vistas de usuario */}
      {(userViews.length > 0 || onSaveCurrentView) && (
        <span
          className="mx-1 h-3.5 w-px shrink-0"
          style={{ background: MT.border }}
          aria-hidden
        />
      )}

      {/* Vistas guardadas por el usuario */}
      {userViews.map((uv) => {
        const active = uv.id === activeId;
        return (
          <span key={uv.id} className="group flex shrink-0 items-center gap-0.5">
            <button
              type="button"
              onClick={() => onSelect(uv)}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] transition-colors"
              style={{
                background: active ? MT.brand : "transparent",
                color: active ? "white" : MT.ink3,
                border: `1px solid ${active ? MT.brand : MT.border}`,
              }}
              title={`Vista guardada: ${uv.name}`}
            >
              <span
                className="size-1.5 rounded-full"
                style={{ background: active ? "rgba(255,255,255,0.7)" : MT.ink4 }}
              />
              <span>{uv.name}</span>
            </button>

            {/* Acciones en hover: share + delete */}
            <span className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
              {onShareView ? (
                <button
                  type="button"
                  aria-label={`Copiar enlace de "${uv.name}"`}
                  title="Copiar enlace"
                  onClick={(e) => {
                    e.stopPropagation();
                    onShareView(uv.id);
                  }}
                  className="rounded-full p-0.5"
                  style={{ color: active ? "rgba(255,255,255,0.7)" : MT.ink4 }}
                >
                  <Link2 className="size-3" />
                </button>
              ) : null}
              {onDeleteView ? (
                <button
                  type="button"
                  aria-label={`Eliminar vista "${uv.name}"`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteView(uv.id);
                  }}
                  className="rounded-full p-0.5"
                  style={{ color: active ? "rgba(255,255,255,0.7)" : MT.ink4 }}
                >
                  <svg
                    width="10"
                    height="10"
                    viewBox="0 0 10 10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  >
                    <line x1="2" y1="2" x2="8" y2="8" />
                    <line x1="8" y1="2" x2="2" y2="8" />
                  </svg>
                </button>
              ) : null}
            </span>
          </span>
        );
      })}

      {/* Botón / input para guardar vista actual */}
      {onSaveCurrentView && !showNameInput && (
        <button
          type="button"
          onClick={() => setShowNameInput(true)}
          className="shrink-0 rounded-full px-2 py-0.5 text-[11px] transition-colors hover:bg-mt-surface-2"
          style={{ color: MT.ink4, border: `1px dashed ${MT.border}` }}
          title="Guardar filtros actuales como vista"
        >
          + Guardar vista
        </button>
      )}

      {onSaveCurrentView && showNameInput && (
        <span className="flex shrink-0 items-center gap-1">
          <input
            autoFocus
            value={viewName}
            onChange={(e) => setViewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
              if (e.key === "Escape") {
                setViewName("");
                setShowNameInput(false);
              }
            }}
            className="rounded border px-1.5 py-0.5 text-[11.5px] outline-none focus:ring-1"
            style={{
              width: "8rem",
              borderColor: MT.border,
              color: MT.ink,
              background: MT.surface,
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              ["--tw-ring-color" as any]: MT.brand,
            }}
            placeholder="Nombre de vista..."
          />
          <button
            type="button"
            onClick={handleSave}
            disabled={!viewName.trim()}
            className="rounded px-1.5 py-0.5 text-[11px] transition-colors disabled:opacity-40"
            style={{
              background: MT.brand,
              color: "white",
            }}
          >
            OK
          </button>
          <button
            type="button"
            onClick={() => {
              setViewName("");
              setShowNameInput(false);
            }}
            className="rounded px-1 py-0.5 text-[11px] transition-colors"
            style={{ color: MT.ink4 }}
          >
            ✕
          </button>
        </span>
      )}
    </div>
  );
}

/**
 * System views per Sally §8.7. Counts come from `useFacets` (caller wires).
 *
 * Stage 3 (Wave 11) — añadidas 2 vistas de división.
 */
export const SYSTEM_VIEWS: SavedView[] = [
  { id: "all", name: "Todos", filters: {} },
  { id: "unclassified", name: "Sin clasificar", filters: { family: "unclassified" } },
  {
    id: "pending-es",
    name: "Pendientes ES",
    filters: { translation_status: "pending", translation_lang: "es" },
  },
  { id: "active-only", name: "Sólo activos", filters: { active: true } },
  // Stage 3 — division shortcuts.
  { id: "div-hidro", name: "Hidrosanitario", filters: { division: "hidrosanitario" } },
  { id: "div-industrial", name: "Industrial", filters: { division: "industrial" } },
  { id: "quality-review", name: "Revisar calidad", filters: { data_quality: "partial" } },
];
