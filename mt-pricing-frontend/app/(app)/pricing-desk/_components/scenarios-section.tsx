"use client";

import {
  useScenarios,
  useSaveScenario,
  useLoadScenario,
} from "@/lib/hooks/pricing-desk/use-scenarios";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

interface ScenarioRow {
  id: string;
  slot: string;
  label: string | null;
  snapshot_at: string;
  selling_model: SellingModel;
}

export function ScenariosSection({ channelCode, sellingModel }: Props) {
  const { data: scenarios } = useScenarios(channelCode, sellingModel);
  const save = useSaveScenario(channelCode);
  const load = useLoadScenario(channelCode);

  const slotA = scenarios?.find((s) => s.slot === "A") ?? null;
  const slotB = scenarios?.find((s) => s.slot === "B") ?? null;

  const renderSlot = (slot: "A" | "B", current: ScenarioRow | null) => (
    <div className="flex flex-col gap-1 rounded border border-mt-border bg-mt-surface-2 p-2 text-xs">
      <div className="flex items-baseline justify-between">
        <span className="font-bold text-mt-ink">Slot {slot}</span>
        {current && (
          <span className="mt-mono text-[10px] text-mt-ink-3">
            {new Date(current.snapshot_at).toLocaleString("es-ES", {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </span>
        )}
      </div>
      {current?.label && <div className="text-[11px] text-mt-ink-2">{current.label}</div>}
      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => {
            const labelRaw = window.prompt("Nombre opcional del escenario:");
            const mutateArgs: { slot: "A" | "B"; sellingModel: SellingModel; label?: string } =
              { slot, sellingModel };
            if (labelRaw) mutateArgs.label = labelRaw;
            save.mutate(mutateArgs);
          }}
          disabled={save.isPending}
          className="flex-1 rounded bg-mt-brand px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-white hover:bg-mt-brand-deep disabled:opacity-50"
        >
          Guardar
        </button>
        <button
          type="button"
          onClick={() => load.mutate({ slot, sellingModel })}
          disabled={!current || load.isPending}
          className="flex-1 rounded border border-mt-border bg-white px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-mt-brand-deep hover:bg-mt-brand-soft disabled:opacity-50"
        >
          Cargar
        </button>
      </div>
    </div>
  );

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-3 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        Escenarios A/B
      </div>
      <div className="grid grid-cols-2 gap-2">
        {renderSlot("A", slotA)}
        {renderSlot("B", slotB)}
      </div>
    </section>
  );
}
