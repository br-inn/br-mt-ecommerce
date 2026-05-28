"use client";

import { useMarginTargets } from "@/lib/hooks/pricing-desk/use-margin-targets";

interface Props {
  channelCode: string;
  familyId?: string;
  onFamilyChange: (id: string | undefined) => void;
  signal?: string;
  onSignalChange: (s: string | undefined) => void;
  searchSku: string;
  onSearchSkuChange: (value: string) => void;
  totalShown: number;
  totalAll: number;
}

const SIGNALS = ["PÉRDIDA", "FRÁGIL", "FINO", "ÓPTIMO", "EXCELENTE"];

export function FiltersBar({
  channelCode,
  familyId,
  onFamilyChange,
  signal,
  onSignalChange,
  searchSku,
  onSearchSkuChange,
  totalShown,
  totalAll,
}: Props) {
  const { data: targets } = useMarginTargets(channelCode);
  const families = targets
    ? Array.from(
        new Map(targets.map((t) => [t.family_id, t.family_name])).entries(),
      )
    : [];

  return (
    <div className="flex flex-wrap items-center gap-4 border-b border-mt-border bg-white px-4 py-2">
      <label className="flex items-center gap-2">
        <span className="mt-mono text-[10px] uppercase tracking-wider text-mt-ink-3">Familia</span>
        <select
          value={familyId ?? ""}
          onChange={(e) => onFamilyChange(e.target.value || undefined)}
          className="rounded border border-mt-border bg-white px-2 py-1 text-sm text-mt-ink"
        >
          <option value="">Todas</option>
          {families.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="mt-mono text-[10px] uppercase tracking-wider text-mt-ink-3">Señal</span>
        <select
          value={signal ?? ""}
          onChange={(e) => onSignalChange(e.target.value || undefined)}
          className="rounded border border-mt-border bg-white px-2 py-1 text-sm text-mt-ink"
        >
          <option value="">Todas</option>
          {SIGNALS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2">
        <span className="mt-mono text-[10px] uppercase tracking-wider text-mt-ink-3">SKU</span>
        <input
          type="search"
          value={searchSku}
          onChange={(e) => onSearchSkuChange(e.target.value)}
          placeholder="Buscar SKU…"
          className="mt-mono rounded border border-mt-border bg-white px-2 py-1 text-xs text-mt-ink placeholder:text-mt-ink-4 focus:border-mt-brand focus:outline-none focus:ring-1 focus:ring-mt-brand-soft"
          aria-label="Buscar por SKU"
        />
      </label>

      {(familyId || signal || searchSku) && (
        <button
          type="button"
          onClick={() => {
            onFamilyChange(undefined);
            onSignalChange(undefined);
            onSearchSkuChange("");
          }}
          className="mt-mono rounded border border-mt-border bg-mt-surface-3 px-2 py-1 text-[10px] uppercase tracking-wider text-mt-brand-deep hover:bg-mt-ink hover:text-white"
        >
          ✕ Limpiar
        </button>
      )}

      <span className="mt-mono ml-auto text-xs text-mt-ink-3">
        Mostrando {totalShown} de {totalAll}
      </span>
    </div>
  );
}
