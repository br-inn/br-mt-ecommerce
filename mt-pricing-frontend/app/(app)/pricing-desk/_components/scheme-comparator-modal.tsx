"use client";

import { useEffect } from "react";
import { useProductPrice } from "@/lib/hooks/pricing-desk/use-product-price";
import { SignalBadge } from "./signal-badge";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  sku: string | null;
  onClose: () => void;
}

export function SchemeComparatorModal({ channelCode, sellingModel, sku, onClose }: Props) {
  const { data, isLoading, error } = useProductPrice(channelCode, sku, sellingModel);

  // Close on Esc
  useEffect(() => {
    if (!sku) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sku, onClose]);

  if (!sku) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-mt-ink/70 p-6 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="scheme-comparator-title"
    >
      <div
        className="max-h-[90vh] w-full max-w-4xl overflow-auto rounded-lg bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-baseline justify-between border-b border-mt-border pb-3">
          <div>
            <h2 id="scheme-comparator-title" className="text-lg font-bold text-mt-ink">
              Comparador de esquemas
            </h2>
            <p className="text-sm text-mt-ink-3">
              SKU <code className="mt-mono text-mt-brand-deep">{sku}</code> · modelo{" "}
              {sellingModel.toUpperCase()}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar comparador"
            className="text-mt-ink-3 hover:text-mt-ink"
          >
            ✕
          </button>
        </div>

        {isLoading && <p className="text-mt-ink-3">Cargando comparación…</p>}
        {error && (
          <p className="text-mt-danger">
            Error: {error instanceof Error ? error.message : "unknown"}
          </p>
        )}

        {data && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {data.all_schemes.map((r) => (
              <div
                key={r.fulfillment_scheme}
                className={
                  "rounded border-2 p-4 " +
                  (r.fulfillment_scheme === data.best_scheme?.fulfillment_scheme
                    ? "border-mt-brand bg-mt-brand-soft"
                    : "border-mt-border bg-mt-surface-2")
                }
              >
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="font-bold text-mt-ink">{r.scheme_label}</span>
                  {r.fulfillment_scheme === data.best_scheme?.fulfillment_scheme && (
                    <span className="mt-mono rounded bg-mt-brand px-2 py-0.5 text-[10px] font-bold uppercase text-white">
                      Óptimo
                    </span>
                  )}
                </div>

                <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                  <dt className="text-mt-ink-3">Coste op.</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">
                    {r.cost_op_aed.toFixed(2)}
                  </dd>

                  <dt className="text-mt-ink-3">Precio</dt>
                  <dd className="mt-mono mt-tnum text-right font-bold text-mt-ink">
                    {r.selling_price_aed?.toFixed(2) ?? "—"}
                  </dd>

                  <dt className="text-mt-ink-3">Techo</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink-2">
                    {r.ceiling_aed?.toFixed(2) ?? "—"}
                  </dd>

                  <dt className="text-mt-ink-3">Margen</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">
                    {r.margin_pct.toFixed(0)}%
                  </dd>

                  <dt className="text-mt-ink-3">Benef./ud</dt>
                  <dd
                    className={
                      "mt-mono mt-tnum text-right font-bold " +
                      (r.benefit_per_unit_aed >= 0 ? "text-mt-success" : "text-mt-danger")
                    }
                  >
                    {r.benefit_per_unit_aed > 0 ? "+" : ""}
                    {r.benefit_per_unit_aed.toFixed(2)}
                  </dd>

                  <dt className="text-mt-ink-3">ROI</dt>
                  <dd className="mt-mono mt-tnum text-right text-mt-ink">
                    {r.roi_pct.toFixed(0)}%
                  </dd>

                  <dt className="text-mt-ink-3">Bajo techo</dt>
                  <dd
                    className={
                      "text-right font-bold " +
                      (r.is_publishable ? "text-mt-success" : "text-mt-danger")
                    }
                  >
                    {r.is_publishable ? "Sí" : "NO"}
                  </dd>

                  <dt className="text-mt-ink-3">Señal</dt>
                  <dd className="text-right">
                    <SignalBadge signal={r.signal} />
                  </dd>
                </dl>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
