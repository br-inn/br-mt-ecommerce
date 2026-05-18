"use client";

import * as React from "react";
import { Check, ExternalLink, Package, Ship, Sparkles, X } from "lucide-react";
import { ScorePill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { MatchCandidate } from "@/lib/api/endpoints/matches";
import { MatchAnalysisPanel } from "./match-analysis-panel";

const fmtAED = (n: number | null, decimals = 0) =>
  n == null
    ? "—"
    : `AED ${new Intl.NumberFormat("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n)}`;

const KIND_LABELS: Record<MatchCandidate["kind"], string> = {
  peer: "Peer fabricante",
  drop: "Distribuidor",
  unknown: "Sin clasificar",
};

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5 text-[11px]">
      <span className="w-14 shrink-0 text-right" style={{ color: MT.ink4 }}>
        {label}
      </span>
      <span
        className={/[0-9]/.test(value) ? "mt-mono font-semibold" : "font-medium"}
        style={{ color: MT.ink2 }}
      >
        {value}
      </span>
    </div>
  );
}

export function CandidateCard({
  candidate,
  onValidate,
  onDiscard,
  pending,
}: {
  candidate: MatchCandidate;
  onValidate: () => void;
  onDiscard: () => void;
  pending: boolean;
}) {
  const { brand, external_id, title, kind, price_aed, score, status, delivery_text, specs_jsonb, channel, image_url, source_url, delivery_category, price_confidence_score, pack_units } =
    candidate;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const specs = (specs_jsonb ?? {}) as Record<string, any>;
  const enhanced = (specs._enhanced ?? {}) as Record<string, unknown>;
  const priceNum = price_aed === null ? null : Number(price_aed);
  const packSize = pack_units != null && pack_units > 1 ? pack_units : null;
  const pricePerUnit = packSize != null && priceNum != null ? priceNum / packSize : null;
  const isLongDelivery = delivery_category === "import";
  const isUnknownDelivery = delivery_category === "unknown" || delivery_category === null;
  const deliveryInfo = (specs._delivery ?? {}) as Record<string, unknown>;
  const estimatedDays = deliveryInfo.estimated_days != null ? Number(deliveryInfo.estimated_days) : null;
  const thumbUrl = image_url ?? undefined;
  const isVal = status === "validated";
  const isDis = status === "discarded";
  const borderLeft = isVal ? MT.success : isDis ? MT.danger : "transparent";
  const bg = isVal ? "#F4FBF6" : isDis ? "#FBF5F4" : MT.surface;

  const autoValidate = enhanced.auto_validate === true;
  const llmMethod = enhanced.method as string | undefined;
  const visualVerdict = enhanced.visual_verdict as string | undefined;

  return (
    <div
      className="relative flex items-start gap-3 rounded-lg border p-3.5 transition-shadow hover:shadow-sm"
      style={{ background: bg, borderColor: MT.border }}
    >
      <span
        className="absolute bottom-0 left-0 top-0 w-[3px] rounded-l-lg"
        style={{ background: borderLeft }}
      />

      {/* Thumbnail canal */}
      <div
        className="mt-1 flex h-[72px] w-[72px] shrink-0 items-center justify-center overflow-hidden rounded-[6px] border"
        style={{ background: MT.surface3, borderColor: MT.border }}
      >
        {thumbUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbUrl} alt={title} className="h-full w-full object-contain" />
        ) : (
          <span className="mt-mono text-[9px] font-semibold uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
            {channel === "amazon_uae" ? "AMZ" : "NOO"}
          </span>
        )}
      </div>

      {/* Info principal */}
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="text-[13px] font-semibold" style={{ color: MT.ink }}>
            {brand ?? "—"}
          </span>
          <span
            className="inline-flex h-4 items-center rounded-[3px] border px-1.5 text-[10px] font-medium"
            style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink3 }}
          >
            {KIND_LABELS[kind]}
          </span>
          <span className="mt-mono text-[10px]" style={{ color: MT.ink4 }}>
            {external_id}
          </span>
        </div>
        <p className="mb-2 text-[11.5px] leading-[1.35]" style={{ color: MT.ink3 }}>
          {title}
        </p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
          <SpecRow label="Tipo" value={String(specs?.valve_type ?? specs?.type ?? "—")} />
          <SpecRow label="Material" value={String(specs?.material ?? "—")} />
          <SpecRow label="Tamaño" value={specs?.size ? `${specs.size}"` : "—"} />
          <SpecRow label="PN" value={specs?.pn != null ? `PN${specs.pn}` : "—"} />
          <SpecRow label="Rosca" value={String(specs?.thread ?? specs?.end_connection ?? "—")} />
          {specs?.alloy ? <SpecRow label="Aleación" value={String(specs.alloy)} /> : null}
          {specs?.manufacturer ? <SpecRow label="Fab." value={String(specs.manufacturer)} /> : null}
        </div>
        {/* Reviews */}
        {(specs?.review_rating != null || specs?.review_count != null) && (
          <div className="mt-1.5 flex items-center gap-1.5">
            {specs?.review_rating != null && (
              <span className="mt-mono text-[10px] font-semibold" style={{ color: MT.ink3 }}>
                ★ {specs.review_rating}
              </span>
            )}
            {specs?.review_count != null && (
              <span className="text-[10px]" style={{ color: MT.ink4 }}>
                ({new Intl.NumberFormat("en-US").format(Number(specs.review_count))} reviews)
              </span>
            )}
          </div>
        )}

        {/* Badge de recomendación LLM */}
        {llmMethod && llmMethod !== "deterministic" && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {autoValidate && (
              <span
                className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold"
                style={{ background: MT.successSoft, color: MT.success, border: `1px solid ${MT.successBorder}` }}
              >
                <Sparkles className="size-2.5" /> LLM recomienda validar
              </span>
            )}
            {visualVerdict === "different_type" && (
              <span
                className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold"
                style={{ background: MT.dangerSoft, color: MT.danger, border: `1px solid ${MT.dangerBorder}` }}
              >
                Tipo diferente (visión)
              </span>
            )}
            {visualVerdict === "same_type" && !autoValidate && (
              <span
                className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-[10px] font-medium"
                style={{ background: MT.surface3, color: MT.ink3, border: `1px solid ${MT.border}` }}
              >
                Mismo tipo — revisar specs
              </span>
            )}
          </div>
        )}

        {/* Panel expandible de análisis de match */}
        {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
        <MatchAnalysisPanel enhanced={enhanced as any} />
      </div>

      {/* Precio + score */}
      <div className="flex w-28 shrink-0 flex-col items-end gap-1.5 pt-0.5">
        {/* Precio comparable (por unidad si hay pack, precio directo si no) */}
        <div
          className="mt-mono text-[15px] font-bold tracking-[-0.2px]"
          style={{ color: isLongDelivery ? MT.warning : MT.ink }}
          title={
            packSize != null
              ? `Pack de ${packSize} u — precio por unidad comparable`
              : isLongDelivery
                ? "Precio referencial — entrega larga desde importación"
                : undefined
          }
        >
          {packSize != null ? fmtAED(pricePerUnit, 2) : fmtAED(priceNum)}
        </div>

        {/* Info del pack: precio total × N unidades */}
        {packSize != null && priceNum != null && (
          <div className="flex flex-col items-end gap-0.5">
            <span className="mt-mono text-[9px] font-semibold" style={{ color: MT.ink4 }}>
              / unidad
            </span>
            <span
              className="inline-flex items-center gap-0.5 rounded-[3px] border px-1 py-0.5 text-[9px] font-medium leading-none"
              style={{ background: MT.surface3, borderColor: MT.border, color: MT.ink3 }}
              title={`Precio del pack completo: ${fmtAED(priceNum)}`}
            >
              ×{packSize} u · {fmtAED(priceNum)}
            </span>
          </div>
        )}

        {/* Chip de entrega — prominente cerca del precio */}
        {delivery_category === "local_stock" ? (
          <span
            className="inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[10px] font-semibold leading-none"
            style={{ background: MT.successSoft, color: MT.success, borderColor: MT.successBorder }}
            title={delivery_text ?? undefined}
          >
            <Package className="size-2.5" />
            Stock UAE{estimatedDays != null ? ` · ${estimatedDays}d` : ""}
          </span>
        ) : delivery_category === "regional" ? (
          <span
            className="inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[10px] font-semibold leading-none"
            style={{ background: MT.surface3, color: MT.ink3, borderColor: MT.border }}
            title={delivery_text ?? undefined}
          >
            <Package className="size-2.5" />
            Regional{estimatedDays != null ? ` · ${estimatedDays}d` : ""}
          </span>
        ) : delivery_category === "import" ? (
          <span
            className="inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[10px] font-bold leading-none"
            style={{ background: MT.warningSoft, color: MT.warning, borderColor: MT.warningBorder }}
            title="Precio referencial — importación larga desde fábrica/China. MT tiene stock local: precio no es comparable directo."
          >
            <Ship className="size-2.5" />
            {estimatedDays != null ? `~${estimatedDays} días · Import` : "Importación larga"}
          </span>
        ) : delivery_text ? (
          <span
            className="text-right text-[10px] leading-tight"
            style={{ color: MT.ink4 }}
          >
            {delivery_text}
          </span>
        ) : null}

        {isLongDelivery && (
          <span
            className="inline-flex items-center gap-0.5 rounded-[3px] border px-1 py-0.5 text-[9px] font-semibold leading-none"
            style={{
              background: MT.warningSoft,
              color: MT.warning,
              borderColor: MT.warningBorder,
            }}
          >
            Precio referencial
          </span>
        )}
        {price_confidence_score != null && (
          <span className="mt-mono text-[9px]" style={{ color: isLongDelivery ? MT.warning : MT.ink4 }}>
            Confianza: {price_confidence_score}%
          </span>
        )}
        <ScorePill score={score} size="lg" />
      </div>

      {/* Decisión */}
      <div className="flex w-36 shrink-0 flex-col items-stretch gap-1.5 pt-0.5">
        {isVal ? (
          <span
            className="inline-flex h-7 items-center justify-center gap-1.5 rounded-[5px] border text-[11.5px] font-semibold"
            style={{ color: MT.success, background: MT.successSoft, borderColor: MT.successBorder }}
          >
            <Check className="size-3" strokeWidth={2.5} /> Validado
          </span>
        ) : isDis ? (
          <span
            className="inline-flex h-7 items-center justify-center gap-1.5 rounded-[5px] border text-[11.5px] font-semibold"
            style={{ color: MT.danger, background: MT.dangerSoft, borderColor: MT.dangerBorder }}
          >
            <X className="size-3" strokeWidth={2.5} /> Descartado
          </span>
        ) : (
          <>
            <button
              type="button"
              onClick={onValidate}
              disabled={pending}
              className="inline-flex h-7 cursor-pointer items-center justify-center gap-1.5 rounded-[5px] border px-2.5 text-[12px] font-semibold text-white disabled:opacity-50"
              style={{ background: MT.brand, borderColor: MT.brand }}
            >
              <Check className="size-3" strokeWidth={2.5} /> Validar
            </button>
            <button
              type="button"
              onClick={onDiscard}
              disabled={pending}
              className="inline-flex h-6 cursor-pointer items-center justify-center gap-1 rounded-[5px] border text-[11px] font-medium disabled:opacity-50"
              style={{ color: MT.ink3, borderColor: MT.border }}
            >
              <X className="size-3" /> Descartar
            </button>
          </>
        )}
        {source_url ? (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-mono inline-flex h-5 items-center justify-center gap-1 text-[10px] hover:underline"
            style={{ color: MT.ink4 }}
          >
            <ExternalLink className="size-3" /> {channel === "amazon_uae" ? "Amazon UAE" : "Noon UAE"}
          </a>
        ) : (
          <span
            className="mt-mono inline-flex h-5 items-center justify-center gap-1 text-[10px]"
            style={{ color: MT.ink4 }}
            title={external_id}
          >
            <ExternalLink className="size-3" /> {external_id}
          </span>
        )}
      </div>
    </div>
  );
}
