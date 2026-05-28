"use client";

import { useState } from "react";
import { useApplyOptimization } from "@/lib/hooks/pricing-desk/use-optimize-catalog";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

export function OptimizeSection({ channelCode, sellingModel }: Props) {
  const applyOpt = useApplyOptimization(channelCode);
  const [confirming, setConfirming] = useState(false);

  const handleApply = () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 4000);
      return;
    }
    applyOpt.mutate(sellingModel);
    setConfirming(false);
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Optimización
      </div>
      <button
        type="button"
        onClick={handleApply}
        disabled={applyOpt.isPending}
        className={
          "w-full rounded px-3 py-2 text-sm font-semibold text-white transition " +
          (confirming
            ? "bg-mt-warning hover:bg-mt-warning-deep"
            : "bg-mt-brand hover:bg-mt-brand-deep") +
          " disabled:opacity-50"
        }
      >
        {applyOpt.isPending
          ? "Aplicando…"
          : confirming
            ? "¿Confirmas? — pulsa de nuevo"
            : "★ Optimización completa"}
      </button>
      <p className="mt-2 text-[11px] leading-tight text-mt-ink-3">
        Para cada producto prueba todos los esquemas y el mejor margen bajo
        techo. Persiste como overrides.
      </p>
    </section>
  );
}
