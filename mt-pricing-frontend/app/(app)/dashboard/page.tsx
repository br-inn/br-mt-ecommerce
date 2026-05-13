"use client";

import Link from "next/link";
import {
  Coins,
  Download,
  Filter,
  History,
  MoreHorizontal,
  Plus,
  RefreshCcw,
  Upload,
} from "lucide-react";

import {
  Kbd,
  KpiCard,
  MtButton,
  MtTd,
  MtTh,
  Pill,
  Sparkline,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { useDashboardStats } from "@/lib/hooks/use-dashboard";
import { InventoryKpiWidget } from "@/components/inventario/inventory-kpi-widget";

const TODAY_FORMAT = new Intl.DateTimeFormat("es-ES", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

function fmtPct(v: number | undefined) {
  if (v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v)}%`;
}

export default function DashboardPage() {
  const { data: stats, isLoading, isError, refetch, isFetching } =
    useDashboardStats();

  const today = TODAY_FORMAT.format(new Date());
  const cat = stats?.catalog;
  const tr = stats?.translations;
  const act = stats?.activity;

  const partial = cat?.products_partial ?? 0;
  const blocked = cat?.products_blocked ?? 0;
  const attentionTotal = partial + blocked;

  return (
    <div className="h-full overflow-auto px-6 py-5">
      {/* Hero */}
      <div className="mb-[18px] flex items-end justify-between">
        <div>
          <div
            className="mt-mono mb-1 text-[11px] uppercase tracking-[0.7px]"
            style={{ color: MT.ink4 }}
          >
            {today}
          </div>
          <h1
            className="m-0 text-[22px] font-semibold tracking-[-0.4px]"
            style={{ color: MT.ink }}
          >
            {isLoading ? (
              <MtSkeleton width={520} height={24} />
            ) : (
              <>
                Hola Pablo —{" "}
                <span className="font-semibold" style={{ color: MT.warning }}>
                  {partial} SKUs partial
                </span>
                ,{" "}
                <span className="font-semibold" style={{ color: MT.danger }}>
                  {blocked} blocked
                </span>
                ,{" "}
                <span className="font-semibold" style={{ color: MT.brand }}>
                  {act?.audit_events_24h ?? 0}
                </span>{" "}
                eventos en las últimas 24 h.
              </>
            )}
          </h1>
        </div>
        <div className="flex gap-1.5">
          <MtButton asChild>
            <Link href="/imports">
              <Upload className="size-3.5" />
              Importar PIM
            </Link>
          </MtButton>
          <MtButton icon={<Coins className="size-3.5" />}>Importar costos</MtButton>
          <MtButton
            icon={<RefreshCcw className="size-3.5" />}
            onClick={() => void refetch()}
            disabled={isFetching}
          >
            Recalcular
          </MtButton>
          <MtButton tone="primary" asChild>
            <Link href="/catalogo/nuevo">
              <Plus className="size-3.5" />
              Alta SKU
            </Link>
          </MtButton>
        </div>
      </div>

      {isError ? (
        <div className="mb-3">
          <MtError
            message="No se pudieron cargar los KPIs del dashboard."
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* KPIs */}
      <div className="mb-[18px] grid grid-cols-4 gap-3">
        <KpiCard
          label="Cobertura traducción ES"
          value={isLoading ? <MtSkeleton width={70} height={26} /> : fmtPct(tr?.es_coverage_pct)}
          sub={
            tr ? `${tr.es_approved} / ${cat?.products_total ?? 0} SKUs` : undefined
          }
          tone={tr && tr.es_coverage_pct >= 85 ? "success" : "warning"}
          badge={tr && tr.es_coverage_pct >= 85 ? "OK" : "meta 85%"}
          spark={
            <Sparkline
              color={tr && tr.es_coverage_pct >= 85 ? MT.success : MT.warning}
              data={[88, 89, 90, 90, 91, 92, 92, 93, 93, 94, 94, tr?.es_coverage_pct ?? 94]}
            />
          }
        />
        <KpiCard
          label="Cobertura traducción AR"
          value={isLoading ? <MtSkeleton width={70} height={26} /> : fmtPct(tr?.ar_coverage_pct)}
          sub={
            tr ? `${tr.ar_approved} / ${cat?.products_total ?? 0} SKUs` : undefined
          }
          tone={tr && tr.ar_coverage_pct >= 85 ? "success" : "warning"}
          badge={tr && tr.ar_coverage_pct >= 85 ? "OK" : "meta 85%"}
          spark={
            <Sparkline color={MT.warning} data={[55, 58, 60, 63, 65, 66, 67, 68, 69, 70, 70, tr?.ar_coverage_pct ?? 71]} />
          }
        />
        <KpiCard
          label="SKUs partial / blocked"
          value={isLoading ? <MtSkeleton width={50} height={26} /> : `${attentionTotal}`}
          sub={`${partial} partial · ${blocked} blocked`}
          tone={attentionTotal === 0 ? "success" : attentionTotal > 10 ? "danger" : "warning"}
          badge={attentionTotal === 0 ? "ok" : "atención"}
          spark={
            <Sparkline color={attentionTotal > 10 ? MT.danger : MT.warning} data={[18, 20, 19, 17, 18, 17, 16, 17, 15, 16, 15, attentionTotal]} />
          }
        />
        <KpiCard
          label="Eventos audit 24 h"
          value={
            isLoading ? <MtSkeleton width={50} height={26} /> : `${act?.audit_events_24h ?? 0}`
          }
          sub={
            stats
              ? `${stats.jobs.runs_24h} jobs · ${stats.jobs.failures_24h} fallos`
              : undefined
          }
          tone="brand"
          badge="hoy"
          spark={<Sparkline color={MT.brand} data={[3, 4, 5, 6, 5, 7, 8, 7, 8, 9, 8, act?.audit_events_24h ?? 8]} />}
        />
      </div>

      {/* Inventario widget */}
      <div className="mb-[18px]">
        <InventoryKpiWidget />
      </div>

      {/* Two columns */}
      <div className="grid grid-cols-[1.6fr_1fr] gap-3.5">
        {/* Recent activity (real) */}
        <div
          className="overflow-hidden rounded-lg border bg-mt-surface"
          style={{ borderColor: MT.border }}
        >
          <div
            className="flex items-center justify-between border-b px-4 py-3"
            style={{ borderColor: MT.border }}
          >
            <div className="flex flex-col gap-0.5">
              <span
                className="text-[13.5px] font-semibold tracking-[-0.1px]"
                style={{ color: MT.ink }}
              >
                Eventos recientes
              </span>
              <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
                Últimos cambios registrados en audit log
              </span>
            </div>
            <div className="flex gap-1.5">
              <MtButton size="sm" icon={<Filter className="size-3.5" />}>
                Filtros
              </MtButton>
              <MtButton size="sm" icon={<Download className="size-3.5" />}>
                Exportar
              </MtButton>
            </div>
          </div>

          <div className="overflow-auto">
            <table className="mt-data-table w-full border-collapse">
              <thead>
                <tr>
                  <MtTh style={{ width: 30 }}>{""}</MtTh>
                  <MtTh>Acción</MtTh>
                  <MtTh>Entidad</MtTh>
                  <MtTh>Actor</MtTh>
                  <MtTh>Fecha</MtTh>
                  <MtTh style={{ width: 28 }}>{""}</MtTh>
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={`sk-${i}`}>
                        <MtTd>
                          <MtSkeleton width={20} height={20} />
                        </MtTd>
                        <MtTd>
                          <MtSkeleton width={100} />
                        </MtTd>
                        <MtTd>
                          <MtSkeleton width={140} />
                        </MtTd>
                        <MtTd>
                          <MtSkeleton width={80} />
                        </MtTd>
                        <MtTd>
                          <MtSkeleton width={90} />
                        </MtTd>
                        <MtTd>{""}</MtTd>
                      </tr>
                    ))
                  : null}
                {!isLoading && (act?.recent_events.length ?? 0) > 0
                  ? act!.recent_events.slice(0, 8).map((e) => (
                      <tr key={e.id}>
                        <MtTd>
                          <span
                            className="size-1.5 inline-block rounded-full"
                            style={{ background: MT.brand }}
                          />
                        </MtTd>
                        <MtTd mono className="font-medium" style={{ color: MT.ink }}>
                          {e.action}
                        </MtTd>
                        <MtTd>
                          <Pill tone="ghost">{e.entity_type}</Pill>
                        </MtTd>
                        <MtTd mono style={{ color: MT.ink3 }}>
                          {e.actor_id ? e.actor_id.slice(0, 8) : "system"}
                        </MtTd>
                        <MtTd mono className="text-[11px]" style={{ color: MT.ink3 }}>
                          {new Date(e.event_at).toLocaleString("es-ES", {
                            month: "short",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </MtTd>
                        <MtTd>
                          <MoreHorizontal
                            className="size-3.5 cursor-pointer"
                            style={{ color: MT.ink4 }}
                          />
                        </MtTd>
                      </tr>
                    ))
                  : null}
              </tbody>
            </table>
            {!isLoading && (act?.recent_events.length ?? 0) === 0 ? (
              <MtEmpty
                title="Sin actividad reciente"
                hint="No hay eventos en las últimas 24 horas."
              />
            ) : null}
          </div>

          <div
            className="flex items-center justify-between px-4 py-2 text-[11.5px]"
            style={{ background: MT.surface2, color: MT.ink3 }}
          >
            <span>
              {act?.audit_events_24h ?? 0} eventos en 24 h ·{" "}
              <Link href="/auditoria" className="cursor-pointer" style={{ color: MT.brand }}>
                Ver todos →
              </Link>
            </span>
            <span className="flex items-center gap-1.5">
              <Kbd>j</Kbd>
              <Kbd>k</Kbd> navegar · <Kbd>↵</Kbd> abrir
            </span>
          </div>
        </div>

        {/* Catalog quality breakdown */}
        <div
          className="flex flex-col overflow-hidden rounded-lg border bg-mt-surface"
          style={{ borderColor: MT.border }}
        >
          <div
            className="flex items-center justify-between border-b px-4 py-3"
            style={{ borderColor: MT.border }}
          >
            <div className="flex flex-col gap-0.5">
              <span
                className="text-[13.5px] font-semibold tracking-[-0.1px]"
                style={{ color: MT.ink }}
              >
                Calidad del catálogo
              </span>
              <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
                {cat ? `${cat.products_active} activos · ${cat.products_total} totales` : "—"}
              </span>
            </div>
            <MtButton size="sm" tone="ghost" asChild>
              <Link href="/auditoria">
                <History className="size-3.5" />
                Audit
              </Link>
            </MtButton>
          </div>

          <div className="flex flex-1 flex-col gap-3 px-4 py-4">
            {isLoading || !cat ? (
              <>
                <MtSkeleton width="100%" height={12} />
                <MtSkeleton width="100%" height={12} />
                <MtSkeleton width="100%" height={12} />
              </>
            ) : (
              [
                { l: "Complete", n: cat.products_complete, color: MT.success },
                { l: "Partial", n: cat.products_partial, color: MT.warning },
                { l: "Blocked", n: cat.products_blocked, color: MT.danger },
              ].map((row) => {
                const pct = cat.products_total === 0 ? 0 : (row.n / cat.products_total) * 100;
                return (
                  <div key={row.l} className="flex flex-col gap-1.5">
                    <div className="flex items-baseline justify-between text-[12px]">
                      <span style={{ color: MT.ink2 }}>
                        {row.l} · <span className="mt-mono">{row.n}</span>
                      </span>
                      <span className="mt-mono text-[11.5px]" style={{ color: MT.ink3 }}>
                        {Math.round(pct)}%
                      </span>
                    </div>
                    <div
                      className="h-1.5 w-full overflow-hidden rounded-full"
                      style={{ background: MT.surface3 }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, background: row.color }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div
            className="flex items-center justify-between border-t px-4 py-2 text-[11.5px]"
            style={{ borderColor: MT.border, background: MT.surface2, color: MT.ink3 }}
          >
            <span>
              {stats ? `Actualizado ${new Date(stats.as_of).toLocaleTimeString("es-ES")}` : "—"}
            </span>
            <Link href="/catalogo" className="cursor-pointer" style={{ color: MT.brand }}>
              Ir al catálogo →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
