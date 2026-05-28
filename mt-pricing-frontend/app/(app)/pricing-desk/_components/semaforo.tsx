import { cn } from "@/lib/utils/cn";
import type { CatalogSummary } from "@/lib/api/endpoints/pricing-desk";

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  variant: "neutral" | "success" | "danger" | "warning" | "brand";
}

function KpiCard({ label, value, sub, variant }: KpiCardProps) {
  const dotColor = {
    neutral: "bg-mt-ink-4",
    success: "bg-mt-success",
    danger: "bg-mt-danger",
    warning: "bg-mt-warning",
    brand: "bg-mt-brand",
  }[variant];
  return (
    <div className="flex items-center gap-2 border-r border-mt-border-strong/30 bg-mt-ink/95 px-3 py-2 last:border-r-0">
      <div className={cn("h-8 w-1.5 rounded-sm", dotColor)} />
      <div className="min-w-0">
        <div className="mt-mono text-[9px] uppercase tracking-wider text-mt-ink-4">
          {label}
        </div>
        <div className="mt-mono text-lg font-bold leading-tight text-white">{value}</div>
        {sub && <div className="text-[10px] text-mt-ink-4">{sub}</div>}
      </div>
    </div>
  );
}

export function Semaforo({ summary }: { summary: CatalogSummary["semaforo"] }) {
  const byScheme = summary.by_scheme;
  return (
    <div className="sticky top-0 z-10 grid grid-cols-2 border-b-2 border-mt-brand md:grid-cols-3 lg:grid-cols-6">
      <KpiCard label="Catálogo" value={summary.total} sub="con precio" variant="brand" />
      <KpiCard label="Publicables" value={summary.publishable} sub="bajo el techo" variant="success" />
      <KpiCard label="Bloqueados" value={summary.blocked} sub="superan techo" variant="danger" />
      <KpiCard label="En pérdida" value={summary.in_loss} sub="margen neg." variant="warning" />
      <KpiCard
        label="Esquemas"
        value={`${byScheme["canal_full"] ?? 0}·${byScheme["canal_lastmile"] ?? 0}·${byScheme["merchant_managed"] ?? 0}`}
        sub="full·lastmile·merchant"
        variant="neutral"
      />
      <KpiCard label="Total productos" value={summary.total} sub="incluye no publicables" variant="brand" />
    </div>
  );
}
