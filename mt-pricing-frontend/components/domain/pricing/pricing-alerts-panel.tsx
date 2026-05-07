"use client";

import * as React from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Info } from "lucide-react";

import { Pill, SectionCard } from "@/components/mt/primitives";
import { MtEmpty } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import type { PriceAlert } from "@/lib/api/endpoints/pricing";

interface Props {
  alerts: ReadonlyArray<PriceAlert>;
  className?: string;
}

const SEVERITY_TONE = {
  critical: "danger" as const,
  warning: "warning" as const,
  info: "neutral" as const,
};

const SEVERITY_ORDER: Record<PriceAlert["severity"], number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

/**
 * Panel de alerts critical/warning/info con drill-down por severidad.
 *
 * UX:
 *  - Cabecera muestra resumen `N criticas · M warnings · K info`.
 *  - Cada severidad colapsable; expansión por click muestra el array `meta`
 *    (campos extra del alert en JSON pretty).
 *  - Vacío: MtEmpty con copy explícito.
 */
export function PricingAlertsPanel({ alerts, className }: Props) {
  const sorted = React.useMemo(
    () =>
      [...alerts].sort(
        (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
      ),
    [alerts],
  );
  const counts = React.useMemo(() => {
    return alerts.reduce<Record<PriceAlert["severity"], number>>(
      (acc, a) => {
        acc[a.severity] = (acc[a.severity] ?? 0) + 1;
        return acc;
      },
      { critical: 0, warning: 0, info: 0 },
    );
  }, [alerts]);

  return (
    <SectionCard
      title="Alertas"
      subtitle={`${counts.critical} críticas · ${counts.warning} warnings · ${counts.info} info`}
      {...(className ? { className } : {})}
      actions={
        counts.critical > 0 ? (
          <Pill tone="danger" dot>
            atención requerida
          </Pill>
        ) : counts.warning > 0 ? (
          <Pill tone="warning" dot>
            revisar
          </Pill>
        ) : (
          <Pill tone="success" dot>
            sin issues
          </Pill>
        )
      }
    >
      {sorted.length === 0 ? (
        <MtEmpty
          title="Sin alertas"
          hint="El motor no emitió ningún issue para esta propuesta."
        />
      ) : (
        <ul className="divide-y" style={{ borderColor: MT.border }}>
          {sorted.map((alert, idx) => (
            <AlertRow alert={alert} key={`${alert.code}-${idx}`} />
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function AlertRow({ alert }: { alert: PriceAlert }) {
  const [open, setOpen] = React.useState(alert.severity === "critical");
  const tone = SEVERITY_TONE[alert.severity];
  const extra = React.useMemo(() => {
    const { severity: _s, code: _c, message: _m, ...rest } = alert;
    void _s;
    void _c;
    void _m;
    return rest;
  }, [alert]);
  const hasExtra = Object.keys(extra).length > 0;

  return (
    <li className="px-4 py-3">
      <button
        type="button"
        onClick={() => hasExtra && setOpen((v) => !v)}
        className="flex w-full items-start gap-3 text-left"
        aria-expanded={open}
      >
        <span className="pt-[2px]">
          {alert.severity === "info" ? (
            <Info className="size-4" style={{ color: MT.ink3 }} />
          ) : (
            <AlertTriangle
              className="size-4"
              style={{
                color:
                  alert.severity === "critical" ? MT.danger : MT.warning,
              }}
            />
          )}
        </span>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone={tone}>{alert.severity}</Pill>
            <span
              className="mt-mono text-[11.5px] uppercase tracking-[0.5px]"
              style={{ color: MT.ink3 }}
            >
              {alert.code}
            </span>
          </div>
          <p
            className="mt-1 text-[13px] leading-snug"
            style={{ color: MT.ink2 }}
          >
            {alert.message}
          </p>
        </div>
        {hasExtra ? (
          open ? (
            <ChevronDown className="size-4" style={{ color: MT.ink4 }} />
          ) : (
            <ChevronRight className="size-4" style={{ color: MT.ink4 }} />
          )
        ) : null}
      </button>
      {hasExtra && open ? (
        <pre
          className="mt-2 overflow-x-auto rounded-md border p-2 text-[11px] leading-snug"
          style={{
            backgroundColor: MT.surface2,
            borderColor: MT.border,
            color: MT.ink2,
          }}
        >
          {JSON.stringify(extra, null, 2)}
        </pre>
      ) : null}
    </li>
  );
}
