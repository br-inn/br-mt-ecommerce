/**
 * `/precios/simular` — Pricing studio (what-if simulator) wired to v5.1 motor.
 *
 * Visual layout from the MT Pricing MDM design exploration; data flow uses
 * `pricingApi.simulate` + `pricingApi.propose` exposed via `useSimulatePrice`
 * and `useProposePrice` hooks.
 */
"use client";

import * as React from "react";
import { AlertTriangle, FileText, History, Upload } from "lucide-react";

import { Crumbs, MtButton, Pill } from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  useChannels,
  useProposePrice,
  useSimulatePrice,
} from "@/lib/hooks/pricing/use-pricing";
import type { PricingResult } from "@/lib/api/endpoints/pricing";

function NumericField({
  label,
  value,
  onChange,
  unit,
  hint,
  step = "0.01",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  unit?: string;
  hint?: string;
  step?: string;
}) {
  return (
    <div
      className="flex items-center justify-between border-b border-dashed py-2"
      style={{ borderColor: MT.border }}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-[11.5px]" style={{ color: MT.ink2 }}>
          {label}
        </span>
        {hint ? (
          <span className="mt-mono text-[10.5px]" style={{ color: MT.ink4 }}>
            {hint}
          </span>
        ) : null}
      </div>
      <div className="inline-flex items-center gap-1.5">
        <input
          type="number"
          step={step}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="mt-mono mt-tnum h-[26px] w-[110px] rounded-[4px] border bg-mt-surface px-2 text-right text-[12px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1"
          style={{ borderColor: MT.border, color: MT.ink }}
        />
        <span className="mt-mono w-7 text-[11px]" style={{ color: MT.ink3 }}>
          {unit ?? ""}
        </span>
      </div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
}) {
  return (
    <div
      className="flex items-center justify-between border-b border-dashed py-2"
      style={{ borderColor: MT.border }}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="text-[11.5px]" style={{ color: MT.ink2 }}>
          {label}
        </span>
        {hint ? (
          <span className="mt-mono text-[10.5px]" style={{ color: MT.ink4 }}>
            {hint}
          </span>
        ) : null}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-mono h-[26px] min-w-[110px] rounded-[4px] border bg-mt-surface px-2 text-right text-[12px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1"
        style={{ borderColor: MT.border, color: MT.ink }}
      />
    </div>
  );
}

function ResultCard({
  result,
  isPending,
  isError,
}: {
  result: PricingResult | undefined;
  isPending: boolean;
  isError: boolean;
}) {
  if (isPending) {
    return (
      <div
        className="overflow-hidden rounded-lg border bg-mt-surface p-3"
        style={{ borderColor: MT.border }}
      >
        <div className="mb-2 flex items-baseline gap-1">
          <MtSkeleton width={140} height={24} />
        </div>
        <MtSkeleton width="100%" height={92} />
      </div>
    );
  }
  if (isError || !result) {
    return (
      <div
        className="grid h-[148px] place-items-center rounded-lg border bg-mt-surface text-[12px]"
        style={{ borderColor: MT.border, color: MT.ink3 }}
      >
        Sin resultado todavía. Pulsa <strong className="mx-1">Simular</strong> para calcular.
      </div>
    );
  }

  const marginPct = parseFloat(result.margin_pct) * 100;
  const marginColor =
    marginPct >= 30 ? MT.success : marginPct >= 18 ? MT.warning : MT.danger;

  return (
    <div
      className="overflow-hidden rounded-lg border bg-mt-surface"
      style={{
        borderColor: result.has_critical_alerts
          ? MT.danger
          : result.has_warnings
            ? MT.warning
            : MT.brand,
        boxShadow: `0 0 0 3px ${
          result.has_critical_alerts
            ? MT.dangerSoft
            : result.has_warnings
              ? MT.warningSoft
              : MT.brandSoft
        }`,
      }}
    >
      <div
        className="flex items-center gap-2 border-b px-3 py-2.5"
        style={{ background: MT.surface2, borderColor: MT.border }}
      >
        <span className="text-[12.5px] font-semibold" style={{ color: MT.ink }}>
          Escenario simulado
        </span>
        <Pill tone="brand">v5.1 motor</Pill>
        <span className="flex-1" />
        <Pill
          tone={
            result.has_critical_alerts
              ? "danger"
              : result.has_warnings
                ? "warning"
                : "success"
          }
          dot
        >
          {result.rule_applied}
        </Pill>
      </div>

      <div className="flex flex-col gap-2 p-3">
        <div className="flex items-baseline gap-2">
          <span
            className="mt-tnum text-[28px] font-semibold tracking-[-0.5px]"
            style={{ color: MT.ink }}
          >
            {result.amount}
          </span>
          <span className="mt-mono text-[12px]" style={{ color: MT.ink3 }}>
            AED
          </span>
          <span className="flex-1" />
          <span className="mt-mono text-[12px] font-medium" style={{ color: marginColor }}>
            {marginPct.toFixed(1)}% margen
          </span>
        </div>

        <div
          className="mt-mono whitespace-pre-wrap rounded-md border bg-mt-surface-2 px-2.5 py-2 text-[11px]"
          style={{ borderColor: MT.border, color: MT.ink2 }}
        >
          {result.formula}
        </div>

        {result.alerts.length > 0 ? (
          <div className="mt-1 flex flex-col gap-1">
            {result.alerts.map((a, i) => (
              <div
                key={`${a.code}-${i}`}
                className="flex items-start gap-1.5 rounded-[4px] border px-2 py-1.5 text-[11px]"
                style={{
                  background:
                    a.severity === "critical"
                      ? MT.dangerSoft
                      : a.severity === "warning"
                        ? MT.warningSoft
                        : MT.surface2,
                  borderColor:
                    a.severity === "critical"
                      ? MT.dangerBorder
                      : a.severity === "warning"
                        ? MT.warningBorder
                        : MT.border,
                  color:
                    a.severity === "critical"
                      ? MT.danger
                      : a.severity === "warning"
                        ? MT.warning
                        : MT.ink2,
                }}
              >
                <AlertTriangle className="size-3 shrink-0" />
                <span>
                  <strong className="mr-1">{a.code}</strong>
                  {a.message}
                </span>
              </div>
            ))}
          </div>
        ) : null}

        <div className="grid grid-cols-3 gap-2 pt-1 text-[11px]" style={{ color: MT.ink3 }}>
          <span>cap: {result.cap_applied ? "sí" : "no"}</span>
          <span>floor: {result.floor_applied ? "sí" : "no"}</span>
          <span>velocity: {result.has_velocity_premium ? "sí" : "no"}</span>
        </div>
      </div>
    </div>
  );
}

export default function PricingStudioPage() {
  const [sku, setSku] = React.useState("MTV-1004");
  const [channelCode, setChannelCode] = React.useState("amazon_uae");
  const [schemeCode, setSchemeCode] = React.useState("FBA");
  const [costTotal, setCostTotal] = React.useState("");
  const [fxRate, setFxRate] = React.useState("");
  const [medianAed, setMedianAed] = React.useState("");

  const { data: channels } = useChannels();
  const simulate = useSimulatePrice();
  const propose = useProposePrice();

  const result = simulate.data;

  const onSimulate = () => {
    const overrides: Record<string, unknown> = {};
    if (costTotal) overrides.cost_total = costTotal;
    if (fxRate) overrides.fx_rate = fxRate;
    if (medianAed) overrides.median_aed = medianAed;
    simulate.mutate({
      product_sku: sku,
      channel_code: channelCode,
      scheme_code: schemeCode,
      scenario_overrides: Object.keys(overrides).length > 0 ? overrides : null,
    });
  };

  const onPropose = () => {
    propose.mutate({
      product_sku: sku,
      channel_code: channelCode,
      scheme_code: schemeCode,
    });
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b bg-mt-surface px-6 pt-3" style={{ borderColor: MT.border }}>
        <Crumbs
          items={[
            { label: "Precios" },
            { label: sku || "—", mono: true, bold: true },
            { label: "Pricing studio" },
          ]}
        />
        <div className="flex items-end gap-3 pb-3 pt-2.5">
          <div className="flex flex-1 flex-col gap-1">
            <h1
              className="m-0 text-[18px] font-semibold tracking-[-0.3px]"
              style={{ color: MT.ink }}
            >
              Pricing what-if · {channelCode} · {schemeCode}
            </h1>
            <span className="text-[12px]" style={{ color: MT.ink3 }}>
              Simula con el motor v5.1 sin persistir; envía a aprobación cuando estés listo.
            </span>
          </div>
          <MtButton icon={<History className="size-3.5" />}>Versiones</MtButton>
          <MtButton icon={<FileText className="size-3.5" />}>Notas</MtButton>
          <MtButton
            tone="primary"
            icon={<Upload className="size-3.5" />}
            onClick={onPropose}
            disabled={propose.isPending || !sku}
          >
            {propose.isPending ? "Enviando…" : "Enviar a aprobación"}
          </MtButton>
        </div>
      </div>

      {/* Body */}
      <div className="grid flex-1 grid-cols-[320px_1fr] gap-4 overflow-auto px-6 py-4">
        {/* Inputs */}
        <div className="flex flex-col gap-3">
          <div
            className="rounded-lg border bg-mt-surface px-3.5 py-3"
            style={{ borderColor: MT.border }}
          >
            <div className="mb-1.5 text-xs font-semibold" style={{ color: MT.ink }}>
              Producto
            </div>
            <TextField label="SKU" value={sku} onChange={setSku} hint="ej. MTV-1004" />
            <div
              className="flex items-center justify-between border-b border-dashed py-2"
              style={{ borderColor: MT.border }}
            >
              <span className="text-[11.5px]" style={{ color: MT.ink2 }}>
                Canal
              </span>
              <select
                value={channelCode}
                onChange={(e) => setChannelCode(e.target.value)}
                className="mt-mono h-[26px] min-w-[110px] rounded-[4px] border bg-mt-surface px-2 text-[12px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1"
                style={{ borderColor: MT.border, color: MT.ink }}
              >
                {(channels ?? []).map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.code}
                  </option>
                ))}
                {(!channels || channels.length === 0) && (
                  <>
                    <option value="amazon_uae">amazon_uae</option>
                    <option value="noon_uae">noon_uae</option>
                    <option value="b2b_uae">b2b_uae</option>
                  </>
                )}
              </select>
            </div>
            <TextField label="Esquema" value={schemeCode} onChange={setSchemeCode} hint="FBA / FBM / SELF" />
            <div className="flex items-center justify-end pt-2">
              <MtButton
                tone="primary"
                size="sm"
                onClick={onSimulate}
                disabled={simulate.isPending || !sku}
              >
                {simulate.isPending ? "Simulando…" : "Simular"}
              </MtButton>
            </div>
          </div>

          <div
            className="rounded-lg border bg-mt-surface px-3.5 py-3"
            style={{ borderColor: MT.border }}
          >
            <div className="mb-1.5 text-xs font-semibold" style={{ color: MT.ink }}>
              Overrides (opcional)
            </div>
            <NumericField
              label="cost_total"
              value={costTotal}
              onChange={setCostTotal}
              unit="AED"
              hint="reemplaza coste landed"
            />
            <NumericField
              label="fx_rate EUR→AED"
              value={fxRate}
              onChange={setFxRate}
              unit=""
              step="0.0001"
              hint="hoy 08:00 GMT por defecto"
            />
            <NumericField
              label="median_aed"
              value={medianAed}
              onChange={setMedianAed}
              unit="AED"
              hint="precio mediano de mercado"
            />
            {(costTotal || fxRate || medianAed) ? (
              <div className="flex justify-end pt-1">
                <MtButton
                  size="sm"
                  tone="ghost"
                  onClick={() => {
                    setCostTotal("");
                    setFxRate("");
                    setMedianAed("");
                  }}
                >
                  Limpiar overrides
                </MtButton>
              </div>
            ) : null}
          </div>
        </div>

        {/* Result */}
        <div className="flex flex-col gap-3.5">
          {simulate.isError ? (
            <MtError
              message={`Simulación falló: ${(simulate.error as Error).message}`}
              onRetry={onSimulate}
            />
          ) : null}

          <ResultCard
            result={result}
            isPending={simulate.isPending}
            isError={simulate.isError}
          />

          {result ? (
            <div
              className="overflow-hidden rounded-lg border bg-mt-surface"
              style={{ borderColor: MT.border }}
            >
              <div
                className="border-b px-3.5 py-2.5 text-[12.5px] font-semibold"
                style={{ borderColor: MT.border, color: MT.ink }}
              >
                Breakdown — desglose v5.1
              </div>
              <pre
                className="mt-mono overflow-auto px-3.5 py-3 text-[11px] leading-[1.6]"
                style={{ background: MT.surface2, color: MT.ink2 }}
              >
                {JSON.stringify(result.breakdown, null, 2)}
              </pre>
            </div>
          ) : null}

          {result && (result.has_critical_alerts || parseFloat(result.margin_pct) * 100 < 30) ? (
            <div
              className="flex items-center gap-3 rounded-lg border px-4 py-3"
              style={{ background: MT.brandSoft, borderColor: MT.brandBorder }}
            >
              <AlertTriangle className="size-4 shrink-0" style={{ color: MT.brand }} />
              <div className="flex flex-1 flex-col gap-0.5">
                <span className="text-[13px] font-semibold" style={{ color: MT.ink }}>
                  Esta propuesta puede requerir aprobación del Gerente.
                </span>
                <span className="text-[11.5px]" style={{ color: MT.ink2 }}>
                  Margen / alertas fuera del umbral. SLA típico: <strong>12 h</strong>.
                </span>
              </div>
              <MtButton
                tone="primary"
                icon={<Upload className="size-3.5" />}
                onClick={onPropose}
                disabled={propose.isPending}
              >
                {propose.isPending ? "Enviando…" : "Enviar a aprobación"}
              </MtButton>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
