"use client";

import * as React from "react";
import { ChevronDown, ChevronUp, Search, Cpu, Eye, BarChart2, Truck } from "lucide-react";
import { MT } from "@/components/mt/tokens";

// ─── Tipos ───────────────────────────────────────────────────────────────────

type BreakdownEntry = {
  matched: boolean;
  pts: number;
  max: number;
  note?: string;
};

type DeliveryInfo = {
  category: "local_stock" | "regional" | "import" | "unknown";
  estimated_days: number | null;
  price_confidence_score: number;
  note: string;
};

type Enhanced = {
  score?: number;
  method?: string;
  auto_validate?: boolean;
  llm_confidence?: number;
  visual_verdict?: string;
  llm_specs?: Record<string, unknown> | null;
  breakdown?: Record<string, BreakdownEntry> | null;
  llm_query?: string | null;
  delivery?: DeliveryInfo | null;
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const METHOD_LABELS: Record<string, string> = {
  deterministic: "Determinista (Capa 0)",
  llm_enriched: "LLM enriquecido (Capa 1)",
  vision_rejected: "Visión rechazó (Capa 2)",
  human_queue: "Cola humana (Capa 2)",
};

const VERDICT_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  same_type: { label: "Mismo tipo", color: MT.success, bg: MT.successSoft },
  different_type: { label: "Tipo diferente", color: MT.danger, bg: MT.dangerSoft },
  uncertain: { label: "Incierto", color: MT.ink3, bg: MT.surface3 },
};

const DELIVERY_LABELS: Record<string, { label: string; color: string; bg: string; border: string }> = {
  local_stock: { label: "Stock UAE/GCC", color: MT.success, bg: MT.successSoft, border: MT.successBorder },
  regional: { label: "Entrega regional", color: MT.ink2, bg: MT.surface3, border: MT.border },
  import: { label: "Importación larga", color: MT.warning, bg: MT.warningSoft, border: MT.warningBorder },
  unknown: { label: "Sin info entrega", color: MT.ink3, bg: MT.surface3, border: MT.border },
};

function pct(pts: number, max: number) {
  return max > 0 ? Math.round((pts / max) * 100) : 0;
}

// ─── Secciones ───────────────────────────────────────────────────────────────

function SectionHeader({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="mb-1.5 flex items-center gap-1.5">
      <span style={{ color: MT.ink4 }}>{icon}</span>
      <span className="text-[10px] font-semibold uppercase tracking-[0.6px]" style={{ color: MT.ink4 }}>
        {label}
      </span>
    </div>
  );
}

function ScoreBar({ dim, entry }: { dim: string; entry: BreakdownEntry }) {
  const fill = pct(entry.pts, entry.max);
  const color = entry.matched ? MT.success : entry.pts > 0 ? MT.warning : MT.danger;
  return (
    <div className="grid grid-cols-[120px_1fr_40px] items-center gap-2">
      <span className="truncate text-right text-[10px]" style={{ color: MT.ink3 }}>
        {dim}
      </span>
      <div className="h-[6px] overflow-hidden rounded-full" style={{ background: MT.surface3 }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${fill}%`, background: color }}
        />
      </div>
      <span className="mt-mono text-right text-[10px]" style={{ color: MT.ink3 }}>
        {entry.pts}/{entry.max}
      </span>
    </div>
  );
}

// ─── Panel principal ─────────────────────────────────────────────────────────

export function MatchAnalysisPanel({ enhanced }: { enhanced: Enhanced }) {
  const [open, setOpen] = React.useState(false);

  const { method, llm_confidence, visual_verdict, llm_specs, breakdown, llm_query, delivery } = enhanced;

  // No mostrar si no hay nada de interés
  const hasContent = method || breakdown || llm_specs || llm_query || delivery;
  if (!hasContent) return null;

  const methodLabel = method ? (METHOD_LABELS[method] ?? method) : null;
  const verdictInfo = visual_verdict ? VERDICT_LABELS[visual_verdict] : null;

  return (
    <div className="mt-2 overflow-hidden rounded-[6px] border" style={{ borderColor: MT.border }}>
      {/* Toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-1.5 transition-colors hover:bg-opacity-60"
        style={{ background: MT.surface3 }}
      >
        <span className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
          <BarChart2 className="size-3" />
          Análisis de match
        </span>
        <span style={{ color: MT.ink4 }}>
          {open ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </span>
      </button>

      {open && (
        <div className="space-y-3 p-3" style={{ background: MT.surface }}>

          {/* Query usada */}
          {llm_query && (
            <div>
              <SectionHeader icon={<Search className="size-3" />} label="Query de búsqueda" />
              <p
                className="mt-mono rounded-[4px] border px-2 py-1 text-[10.5px]"
                style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink2 }}
              >
                {llm_query}
              </p>
            </div>
          )}

          {/* Método + confianza */}
          {methodLabel && (
            <div>
              <SectionHeader icon={<Cpu className="size-3" />} label="Decisión del pipeline" />
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="rounded-[4px] border px-1.5 py-0.5 text-[10px] font-medium"
                  style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink2 }}
                >
                  {methodLabel}
                </span>
                {llm_confidence != null && (
                  <span className="text-[10px]" style={{ color: MT.ink3 }}>
                    Confianza LLM:{" "}
                    <span className="mt-mono font-semibold" style={{ color: MT.ink }}>
                      {Math.round(llm_confidence * 100)}%
                    </span>
                  </span>
                )}
                {verdictInfo && (
                  <span
                    className="rounded-[4px] border px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      background: verdictInfo.bg,
                      color: verdictInfo.color,
                      borderColor: verdictInfo.color + "40",
                    }}
                  >
                    <Eye className="mr-1 inline size-2.5" />
                    Visión: {verdictInfo.label}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Specs extraídas por LLM */}
          {llm_specs && Object.keys(llm_specs).length > 0 && (
            <div>
              <SectionHeader icon={<Cpu className="size-3" />} label="Specs extraídas por LLM" />
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                {Object.entries(llm_specs).map(([k, v]) =>
                  v != null ? (
                    <div key={k} className="flex items-baseline gap-1.5 text-[10px]">
                      <span className="w-20 shrink-0 text-right" style={{ color: MT.ink4 }}>
                        {k}
                      </span>
                      <span className="font-medium" style={{ color: MT.ink2 }}>
                        {String(v)}
                      </span>
                    </div>
                  ) : null
                )}
              </div>
            </div>
          )}

          {/* Confiabilidad de precio por entrega */}
          {delivery && (
            <div>
              <SectionHeader icon={<Truck className="size-3" />} label="Precio vs. stock UAE" />
              <div className="flex flex-wrap items-center gap-2">
                {(() => {
                  const d = (DELIVERY_LABELS[delivery.category] ?? DELIVERY_LABELS["unknown"])!;
                  return (
                    <span
                      className="rounded-[4px] border px-1.5 py-0.5 text-[10px] font-medium"
                      style={{ background: d.bg, color: d.color, borderColor: d.border }}
                    >
                      {d.label}
                    </span>
                  );
                })()}
                {delivery.estimated_days != null && (
                  <span className="text-[10px]" style={{ color: MT.ink3 }}>
                    ~{delivery.estimated_days} días
                  </span>
                )}
                <span className="mt-mono text-[10px] font-semibold" style={{ color: delivery.price_confidence_score >= 70 ? MT.success : delivery.price_confidence_score >= 50 ? MT.ink2 : MT.warning }}>
                  Confianza precio: {delivery.price_confidence_score}%
                </span>
              </div>
              {delivery.note && (
                <p className="mt-1 text-[10px] leading-snug" style={{ color: MT.ink4 }}>
                  {delivery.note}
                </p>
              )}
            </div>
          )}

          {/* Scoring breakdown */}
          {breakdown && Object.keys(breakdown).length > 0 && (
            <div>
              <SectionHeader icon={<BarChart2 className="size-3" />} label="Scoring por dimensión" />
              <div className="space-y-1">
                {Object.entries(breakdown)
                  .filter(([, v]) => typeof v === "object" && v !== null && "max" in v && (v as BreakdownEntry).max > 0)
                  .sort(([, a], [, b]) => (b as BreakdownEntry).max - (a as BreakdownEntry).max)
                  .map(([dim, entry]) => (
                    <ScoreBar key={dim} dim={dim} entry={entry as BreakdownEntry} />
                  ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
