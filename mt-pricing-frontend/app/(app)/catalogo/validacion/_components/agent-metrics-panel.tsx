"use client";

import * as React from "react";
import { MT } from "@/components/mt/tokens";
import {
  useAgentConfig,
  useAgentMetrics,
  useUpdateAgentConfig,
} from "@/lib/hooks/matches/use-match-agent";

export function AgentMetricsPanel() {
  const { data: metrics } = useAgentMetrics();
  const { data: config } = useAgentConfig();
  const update = useUpdateAgentConfig();

  if (!metrics || !config) return null;

  const pct = Math.min(100, Math.round((metrics.golden_labels_total / metrics.min_labels_gate) * 100));

  return (
    <div
      className="flex flex-wrap items-center gap-4 border-b px-6 py-2.5"
      style={{ background: MT.surface2, borderColor: MT.border }}
    >
      <span
        className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.5px]"
        style={{ color: MT.ink4 }}
      >
        🤖 Agente · modo {config.mode === "shadow" ? "sombra" : "activo"}
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Labels:{" "}
        <b style={{ color: MT.ink }}>
          {metrics.golden_labels_total}
        </b>{" "}
        / {metrics.min_labels_gate} ({pct}%)
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Precisión sombra:{" "}
        <b style={{ color: MT.ink }}>
          {metrics.shadow_precision != null
            ? `${Math.round(metrics.shadow_precision * 100)}%`
            : "—"}
        </b>
      </span>
      <span className="text-[11px]" style={{ color: MT.ink3 }}>
        Calibrador:{" "}
        <b style={{ color: MT.ink }}>
          {metrics.calibrator_version ?? "sin entrenar"}
        </b>
      </span>
      {config.mode === "shadow" && metrics.gate_reached && (
        <button
          type="button"
          disabled={update.isPending}
          onClick={() => update.mutate({ mode: "active" })}
          className="inline-flex items-center rounded-[6px] px-3 py-1 text-[12px] text-white font-medium disabled:opacity-50"
          style={{ background: MT.brand }}
        >
          Activar agente
        </button>
      )}
      {config.mode === "active" && (
        <button
          type="button"
          disabled={update.isPending}
          onClick={() => update.mutate({ mode: "shadow" })}
          className="inline-flex items-center rounded-[6px] border px-3 py-1 text-[12px] font-medium disabled:opacity-50"
          style={{ borderColor: MT.border, color: MT.ink3 }}
        >
          Volver a sombra
        </button>
      )}
    </div>
  );
}
