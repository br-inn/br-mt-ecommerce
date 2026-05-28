"use client";

import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  onChannelChange: (code: string) => void;
  sellingModel: SellingModel;
  onSellingModelChange: (m: SellingModel) => void;
}

const CHANNELS = [
  { code: "amazon_uae", label: "Amazon UAE", emoji: "🛒" },
  { code: "noon_uae", label: "Noon UAE", emoji: "🟡" },
];

const SELLING_MODELS: Array<{ value: SellingModel; label: string }> = [
  { value: "b2c", label: "B2C — por unidad" },
  { value: "b2b", label: "B2B — por caja" },
];

export function PricingHeader({
  channelCode,
  onChannelChange,
  sellingModel,
  onSellingModelChange,
}: Props) {
  return (
    <header className="mt-brand-stripe flex items-center gap-4 px-6 py-3 text-white">
      <div className="mt-mono text-xs uppercase tracking-widest text-mt-brand-soft opacity-80">
        MT Middle East · Pricing Intelligence
      </div>
      <h1 className="font-mt-sans text-lg font-bold tracking-wide">PRICING DESK</h1>
      <div className="ml-auto flex items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="mt-mono text-[10px] uppercase tracking-wider opacity-80">Canal</span>
          <select
            value={channelCode}
            onChange={(e) => onChannelChange(e.target.value)}
            className="mt-mono rounded border border-white/20 bg-white/10 px-2 py-1 text-sm font-medium text-white backdrop-blur-sm hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-white/40"
          >
            {CHANNELS.map((c) => (
              <option key={c.code} value={c.code} className="text-mt-ink">
                {c.emoji} {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="mt-mono text-[10px] uppercase tracking-wider opacity-80">Modelo</span>
          <select
            value={sellingModel}
            onChange={(e) => onSellingModelChange(e.target.value as SellingModel)}
            className="mt-mono rounded border border-white/20 bg-white/10 px-2 py-1 text-sm font-medium text-white backdrop-blur-sm hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-white/40"
          >
            {SELLING_MODELS.map((m) => (
              <option key={m.value} value={m.value} className="text-mt-ink">
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </header>
  );
}
