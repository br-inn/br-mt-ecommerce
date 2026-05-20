"use client";

import * as React from "react";
import { MT } from "@/components/mt/tokens";
import type { MatchCandidate } from "@/lib/api/endpoints/matches";

interface BulkAcceptBarProps {
  items: MatchCandidate[];
  busy: boolean;
  onAcceptAll: (ids: string[]) => void;
}

export function BulkAcceptBar({ items, busy, onAcceptAll }: BulkAcceptBarProps) {
  const recommended = React.useMemo(
    () =>
      items.filter(
        (c) =>
          c.status === "pending" &&
          (c.review_priority === "low" ||
            (c.specs_jsonb as Record<string, unknown> | undefined)?._enhanced != null &&
              ((c.specs_jsonb as { _enhanced?: { auto_validate?: boolean } })._enhanced
                ?.auto_validate === true)),
      ),
    [items],
  );

  if (recommended.length === 0) return null;

  return (
    <div
      className="flex items-center justify-between gap-3 border-b px-6 py-2"
      style={{ background: "#EFF6FF", borderColor: "#BFDBFE" }}
    >
      <span className="flex items-center gap-1.5 text-[12px] font-medium" style={{ color: "#1D4ED8" }}>
        ✦ El agente recomienda validar {recommended.length} candidato
        {recommended.length !== 1 ? "s" : ""}
      </span>
      <button
        type="button"
        disabled={busy}
        onClick={() => onAcceptAll(recommended.map((c) => c.id))}
        className="inline-flex items-center rounded-[6px] px-3 py-1 text-[12px] text-white font-medium disabled:opacity-50"
        style={{ background: MT.brand }}
      >
        Aceptar {recommended.length} recomendado{recommended.length !== 1 ? "s" : ""}
      </button>
    </div>
  );
}
