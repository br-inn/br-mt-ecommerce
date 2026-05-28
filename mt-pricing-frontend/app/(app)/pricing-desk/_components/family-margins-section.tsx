"use client";

import { NumericStepper } from "@/components/data/numeric-stepper";
import {
  useMarginTargets,
  useUpsertMarginTarget,
} from "@/lib/hooks/pricing-desk/use-margin-targets";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

const PRESETS = [0, 15, 25, 40];

export function FamilyMarginsSection({ channelCode, sellingModel }: Props) {
  const { data: targets } = useMarginTargets(channelCode);
  const upsert = useUpsertMarginTarget(channelCode);

  const filtered =
    targets?.filter((t) => t.selling_model === sellingModel) ?? [];

  const handleChange = (familyId: string, value: number) => {
    upsert.mutate({
      family_id: familyId,
      selling_model: sellingModel,
      margin_target_pct: value,
    });
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Margen por familia
      </div>
      {filtered.length === 0 && (
        <p className="text-xs text-mt-ink-3">
          No hay márgenes objetivo configurados para este canal+modelo.
        </p>
      )}
      {filtered.map((t) => (
        <div key={t.id} className="mb-3">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-xs font-semibold text-mt-ink">
              {t.family_name}
            </span>
            <span className="mt-mono text-[10px] font-bold text-mt-brand-deep">
              {Number(t.margin_target_pct).toFixed(0)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <NumericStepper
              value={Number(t.margin_target_pct)}
              onChange={(v) => handleChange(t.family_id, v)}
              min={-10}
              max={80}
              step={1}
              decimals={0}
              suffix="%"
              size="sm"
            />
            <div className="flex gap-1">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => handleChange(t.family_id, p)}
                  className="mt-mono rounded border border-mt-border bg-white px-1.5 py-0.5 text-[10px] font-bold text-mt-brand-deep hover:bg-mt-ink hover:text-white"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
