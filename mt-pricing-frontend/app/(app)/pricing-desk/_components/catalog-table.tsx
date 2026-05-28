"use client";

import { NumericStepper } from "@/components/data/numeric-stepper";
import { SignalBadge } from "./signal-badge";
import type { CatalogSummary, SellingModel } from "@/lib/api/endpoints/pricing-desk";
import {
  useUpsertMarginOverride,
  useDeleteMarginOverride,
} from "@/lib/hooks/pricing-desk/use-margin-targets";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
  rows: CatalogSummary["rows"];
  selectedSkus: Set<string>;
  onToggleSku: (sku: string) => void;
  onToggleAll: (allCurrentlyShown: string[], selectAll: boolean) => void;
  onOpenComparator: (sku: string) => void;
}

export function CatalogTable({
  channelCode,
  sellingModel,
  rows,
  selectedSkus,
  onToggleSku,
  onToggleAll,
  onOpenComparator,
}: Props) {
  const upsertOverride = useUpsertMarginOverride(channelCode);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const deleteOverride = useDeleteMarginOverride(channelCode);

  const handleMarginChange = (sku: string, newMargin: number) => {
    upsertOverride.mutate({
      sku,
      body: { margin_override_pct: newMargin, selling_model: sellingModel },
    });
  };

  return (
    <div className="overflow-auto border border-mt-border bg-white">
      <table className="mt-data-table w-full text-sm">
        <thead>
          <tr className="bg-mt-ink text-white">
            <th className="px-3 py-2 w-8">
              <input
                type="checkbox"
                checked={rows.length > 0 && rows.every((r) => selectedSkus.has(r.sku))}
                onChange={(e) => onToggleAll(rows.map((r) => r.sku), e.target.checked)}
                aria-label="Seleccionar todos"
              />
            </th>
            <th className="px-2 py-2 w-6" aria-label="Comparar"></th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">SKU</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Esquema</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Coste op.</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Techo</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Margen</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Precio</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">Benef./ud</th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">ROI</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase">Señal</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.sku}
              className={
                r.is_publishable
                  ? "border-b border-mt-border"
                  : "border-b border-mt-border bg-mt-danger-soft/30"
              }
            >
              <td className="px-3 py-1.5">
                <input
                  type="checkbox"
                  checked={selectedSkus.has(r.sku)}
                  onChange={() => onToggleSku(r.sku)}
                  aria-label={`Seleccionar ${r.sku}`}
                />
              </td>
              <td className="px-2 py-1.5 text-center">
                <button
                  type="button"
                  onClick={() => onOpenComparator(r.sku)}
                  className="text-mt-brand-deep hover:text-mt-brand"
                  aria-label={`Comparar esquemas para ${r.sku}`}
                  title="Comparar esquemas"
                >
                  ▸
                </button>
              </td>
              <td className="mt-mono px-3 py-1.5 text-xs text-mt-brand-deep">{r.sku}</td>
              <td className="px-3 py-1.5 text-xs">
                <span className="mt-mono rounded bg-mt-brand-soft px-2 py-0.5 text-[10px] font-bold text-mt-brand-deep">
                  {r.scheme_label}
                </span>
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.cost_op_aed.toFixed(2)}
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.ceiling_aed?.toFixed(2) ?? "—"}
              </td>
              <td className="px-3 py-1.5">
                <NumericStepper
                  value={r.margin_pct}
                  onChange={(v) => handleMarginChange(r.sku, v)}
                  min={-10}
                  max={80}
                  step={1}
                  decimals={0}
                  suffix="%"
                  size="sm"
                  aria-label={`Margen de ${r.sku}`}
                />
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs font-semibold">
                {r.selling_price_aed?.toFixed(2) ?? "—"}
              </td>
              <td
                className={`mt-mono mt-tnum px-3 py-1.5 text-right text-xs font-semibold ${r.benefit_per_unit_aed < 0 ? "text-mt-danger" : "text-mt-success"}`}
              >
                {r.benefit_per_unit_aed > 0 ? "+" : ""}
                {r.benefit_per_unit_aed.toFixed(2)}
              </td>
              <td className="mt-mono mt-tnum px-3 py-1.5 text-right text-xs">
                {r.roi_pct.toFixed(0)}%
              </td>
              <td className="px-3 py-1.5">
                <SignalBadge signal={r.signal} />
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={11} className="px-3 py-6 text-center text-sm text-mt-ink-3">
                No hay productos con los filtros actuales.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
