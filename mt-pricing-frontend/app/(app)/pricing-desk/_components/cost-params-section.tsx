"use client";

import { useState } from "react";
import { NumericStepper } from "@/components/data/numeric-stepper";
import {
  usePricingParams,
  useUpdateRouteParams,
  useUpdateFeeParams,
} from "@/lib/hooks/pricing-desk/use-pricing-params";

const ESCALONES = [
  {
    title: "1 · Compra a MT",
    params: [
      {
        key: "mt_discount_pct",
        label: "Descuento factura",
        source: "fee" as const,
        pct: true,
        max: 50,
      },
      {
        key: "fx_rate",
        label: "Tipo cambio EUR→AED",
        source: "route" as const,
        pct: false,
        step: 0.01,
        max: 6,
        decimals: 2,
      },
      {
        key: "fx_buffer_pct",
        label: "Colchón FX",
        source: "route" as const,
        pct: true,
        max: 15,
      },
    ],
  },
  {
    title: "2 · Importación y almacén",
    params: [
      {
        key: "import_tariff_pct",
        label: "Arancel importación",
        source: "route" as const,
        pct: true,
        max: 50,
      },
      {
        key: "local_warehouse_pct",
        label: "Almacén propio",
        source: "route" as const,
        pct: true,
        max: 20,
      },
      {
        key: "handling_pct",
        label: "Manipulación",
        source: "route" as const,
        pct: true,
        max: 20,
      },
      {
        key: "freight_rate_per_kg",
        label: "Flete €/kg",
        source: "route" as const,
        pct: false,
        step: 0.1,
        decimals: 2,
        max: 50,
      },
      {
        key: "freight_min_aed",
        label: "Flete mínimo AED",
        source: "route" as const,
        pct: false,
        step: 5,
        decimals: 0,
        max: 5000,
      },
    ],
  },
  {
    title: "3 · Comisiones del canal",
    params: [
      {
        key: "commission_pct",
        label: "Referral",
        source: "fee" as const,
        pct: true,
        max: 30,
      },
      {
        key: "vat_pct",
        label: "IVA UAE",
        source: "fee" as const,
        pct: true,
        max: 30,
      },
      {
        key: "advertising_pct",
        label: "Publicidad PPC",
        source: "fee" as const,
        pct: true,
        max: 30,
      },
      {
        key: "returns_pct",
        label: "Devoluciones",
        source: "fee" as const,
        pct: true,
        max: 15,
      },
    ],
  },
  {
    title: "4 · Logística del canal",
    params: [
      {
        key: "storage_multiplier",
        label: "Mult. almacén",
        source: "fee" as const,
        pct: false,
        step: 0.1,
        decimals: 2,
        max: 5,
      },
    ],
  },
];

export function CostParamsSection({ channelCode }: { channelCode: string }) {
  const { data: params } = usePricingParams(channelCode);
  const updateRoute = useUpdateRouteParams(channelCode);
  const updateFee = useUpdateFeeParams(channelCode);
  const [open, setOpen] = useState(true);

  if (!params) return null;

  const getValue = (key: string, source: "fee" | "route"): number => {
    const src = source === "fee" ? params.fees : params.route;
    return Number((src as Record<string, unknown>)[key] ?? 0);
  };

  const handleChange = (
    key: string,
    source: "fee" | "route",
    value: number,
  ) => {
    if (source === "fee") updateFee.mutate({ [key]: value });
    else updateRoute.mutate({ [key]: value });
  };

  return (
    <section className="border-b border-mt-border">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between bg-mt-surface-2 px-3 py-2 text-left"
      >
        <span className="mt-mono text-xs font-semibold uppercase tracking-wider text-mt-ink">
          ⚙ Parámetros
        </span>
        <span className="text-xs text-mt-brand-deep">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="p-3">
          {ESCALONES.map((escalon) => (
            <div key={escalon.title} className="mb-3">
              <div className="mt-mono mb-2 rounded-r border-l-2 border-mt-brand bg-mt-brand-soft px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-mt-brand-deep">
                {escalon.title}
              </div>
              {escalon.params.map((p) => (
                <div
                  key={p.key}
                  className="mb-1.5 flex items-center justify-between gap-2"
                >
                  <span className="text-xs text-mt-ink-2">{p.label}</span>
                  <NumericStepper
                    value={getValue(p.key, p.source)}
                    onChange={(v) => handleChange(p.key, p.source, v)}
                    min={0}
                    max={p.max ?? 100}
                    step={p.step ?? 0.5}
                    decimals={p.decimals ?? 1}
                    suffix={p.pct ? "%" : ""}
                    size="sm"
                  />
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
