"use client";

import * as React from "react";
import { X } from "lucide-react";

import { MT } from "@/components/mt/tokens";

interface Chip {
  key: string;
  label: string;
}

interface ActiveFiltersBarProps {
  chips: Chip[];
  total: number | null;
  totalUnfiltered: number | null;
  onRemove: (key: string) => void;
  onClearAll: () => void;
}

/**
 * Sally §8.6 — outlined accent style: `MT.brand` 12% bg + `MT.brand` border + text.
 * Shows "1639 → 87" style reduction when both totals are known and a filter is active.
 */
export function ActiveFiltersBar({
  chips,
  total,
  totalUnfiltered,
  onRemove,
  onClearAll,
}: ActiveFiltersBarProps) {
  if (chips.length === 0) return null;
  const showReduction = total !== null && totalUnfiltered !== null && total !== totalUnfiltered;
  return (
    <div
      className="flex flex-wrap items-center gap-1.5 border-b px-3 py-2"
      style={{ borderColor: MT.border, background: MT.surface }}
    >
      <span className="mt-mono text-[10.5px] uppercase tracking-[0.6px]" style={{ color: MT.ink4 }}>
        filtros activos
      </span>
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          onClick={() => onRemove(chip.key)}
          className="flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] hover:bg-mt-surface2"
          style={{
            borderColor: MT.brand,
            color: MT.brand,
            background: `color-mix(in srgb, ${MT.brand} 12%, transparent)`,
          }}
          aria-label={`Quitar ${chip.label}`}
        >
          <span>{chip.label}</span>
          <X className="size-3" />
        </button>
      ))}
      {chips.length >= 2 ? (
        <button
          type="button"
          onClick={onClearAll}
          className="text-[11px] underline-offset-2 hover:underline"
          style={{ color: MT.ink3 }}
        >
          limpiar todo
        </button>
      ) : null}
      {showReduction ? (
        <span
          className="mt-mono ml-auto text-[11px] tabular-nums"
          style={{ color: MT.ink3 }}
        >
          {totalUnfiltered!.toLocaleString()} → {total!.toLocaleString()}
        </span>
      ) : null}
    </div>
  );
}
