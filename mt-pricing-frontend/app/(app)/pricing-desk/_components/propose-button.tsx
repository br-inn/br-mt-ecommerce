"use client";

import { useState } from "react";
import { useProposeSelected } from "@/lib/hooks/pricing-desk/use-propose-prices";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  selectedSkus: Set<string>;
  onProposed: () => void;
}

export function ProposeButton({ channelCode, sellingModel, selectedSkus, onProposed }: Props) {
  const [confirming, setConfirming] = useState(false);
  const propose = useProposeSelected(channelCode);
  const [lastResult, setLastResult] = useState<{
    proposed: number;
    skipped: number;
    errors: number;
  } | null>(null);

  const handleClick = async () => {
    if (selectedSkus.size === 0) return;
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 4000);
      return;
    }
    const result = await propose.mutateAsync({
      skus: Array.from(selectedSkus),
      sellingModel,
    });
    setLastResult({
      proposed: result.proposed,
      skipped: result.skipped,
      errors: result.errors,
    });
    setConfirming(false);
    onProposed();
  };

  const label = (() => {
    if (propose.isPending) return "Enviando…";
    if (confirming) return `¿Proponer ${selectedSkus.size}? — pulsa de nuevo`;
    if (selectedSkus.size === 0) return "Selecciona SKUs para proponer";
    return `↑ Proponer ${selectedSkus.size} a aprobación`;
  })();

  return (
    <div className="flex items-center gap-3 border-b border-mt-border bg-white px-4 py-2">
      <button
        type="button"
        disabled={selectedSkus.size === 0 || propose.isPending}
        onClick={handleClick}
        className={
          "rounded px-3 py-1.5 text-sm font-semibold text-white transition " +
          (confirming ? "bg-mt-warning hover:opacity-90" : "bg-mt-success hover:opacity-90") +
          " disabled:bg-mt-ink-4 disabled:cursor-not-allowed"
        }
      >
        {label}
      </button>
      {lastResult && (
        <span className="mt-mono text-xs text-mt-ink-3">
          {lastResult.proposed} propuestos · {lastResult.skipped} omitidos ·{" "}
          {lastResult.errors} con error
        </span>
      )}
      {propose.error instanceof Error && (
        <span className="mt-mono text-xs text-mt-danger">
          Error: {propose.error.message}
        </span>
      )}
    </div>
  );
}
