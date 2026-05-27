"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { MT } from "@/components/mt/tokens";

export interface SkuQueueEntry {
  sku: string;
  candidateCount: number;
  bestScore: number | null;
}

interface SkuQueuePanelProps {
  entries: SkuQueueEntry[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  collapsed: boolean;
  onToggle: () => void;
}

function ScoreDot({ score }: { score: number | null }) {
  const color =
    score === null
      ? MT.border
      : score >= 70
        ? MT.success
        : score >= 40
          ? MT.warning
          : MT.danger;
  return <span className="mt-0.5 size-2 shrink-0 rounded-full" style={{ background: color }} />;
}

export function SkuQueuePanel({
  entries,
  selectedIndex,
  onSelect,
  collapsed,
  onToggle,
}: SkuQueuePanelProps) {
  const selectedRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  if (collapsed) {
    return (
      <div className="flex items-start pt-1">
        <button
          type="button"
          onClick={onToggle}
          className="flex h-8 w-5 cursor-pointer items-center justify-center rounded-r-md border border-l-0"
          style={{ borderColor: MT.border, background: MT.surface, color: MT.ink3 }}
          title="Mostrar cola de SKUs"
        >
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div
      className="mt-card-lift flex w-[200px] shrink-0 flex-col self-stretch overflow-hidden rounded-lg border bg-mt-surface"
      style={{ borderColor: MT.border }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between border-b px-3 py-2"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <span
          className="mt-mono text-[10.5px] font-semibold uppercase tracking-[0.6px]"
          style={{ color: MT.ink4 }}
        >
          Cola · {entries.length}
        </span>
        <button
          type="button"
          onClick={onToggle}
          className="flex size-5 cursor-pointer items-center justify-center rounded"
          style={{ color: MT.ink4 }}
          title="Colapsar cola"
        >
          <ChevronLeft className="size-3.5" />
        </button>
      </div>

      {/* Lista scrollable */}
      <div className="flex-1 overflow-y-auto">
        {entries.map((entry, idx) => {
          const isSelected = idx === selectedIndex;
          return (
            <button
              key={entry.sku}
              ref={isSelected ? selectedRef : undefined}
              type="button"
              onClick={() => {
                onSelect(idx);
                onToggle();
              }}
              className="flex w-full cursor-pointer items-start gap-2 border-b px-3 py-2 text-left"
              style={{
                borderColor: MT.border,
                background: isSelected ? MT.brandSoft : undefined,
              }}
            >
              <ScoreDot score={entry.bestScore} />
              <div className="min-w-0 flex-1">
                <div
                  className="mt-mono truncate text-[11.5px] font-semibold"
                  style={{ color: isSelected ? MT.brand : MT.ink }}
                >
                  {entry.sku}
                </div>
                <div className="text-[10px]" style={{ color: MT.ink4 }}>
                  {entry.candidateCount} candidato{entry.candidateCount !== 1 ? "s" : ""}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
