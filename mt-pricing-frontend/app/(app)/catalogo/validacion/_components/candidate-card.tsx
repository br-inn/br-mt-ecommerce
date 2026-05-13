"use client";

import * as React from "react";
import { Check, ExternalLink, X } from "lucide-react";
import { ScorePill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { MatchCandidate } from "@/lib/api/endpoints/matches";

const fmtAED = (n: number | null) =>
  n == null
    ? "—"
    : `AED ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n)}`;

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
  const { brand, external_id, title, kind, price_aed, score, status, delivery_text, specs_jsonb } =
    candidate;
  const specs = specs_jsonb as Record<string, string | null | undefined>;
  const priceNum = price_aed === null ? null : Number(price_aed);
  const isVal = status === "validated";
  const isDis = status === "discarded";
  const borderLeft = isVal ? MT.success : isDis ? MT.danger : "transparent";
  const bg = isVal ? "#F4FBF6" : isDis ? "#FBF5F4" : MT.surface;

  return (
    <div
      className="relative flex items-start gap-3 rounded-lg border p-3.5 transition-shadow hover:shadow-sm"
      style={{ background: bg, borderColor: MT.border }}
    >
      <span
        className="absolute bottom-0 left-0 top-0 w-[3px] rounded-l-lg"
        style={{ background: borderLeft }}
      />

      {/* Foto Amazon placeholder */}
      <div
        className="mt-1 flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-[6px] border"
        style={{ background: MT.surface3, borderColor: MT.border }}
      >
        <span className="mt-mono text-[9px] uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
          foto
        </span>
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
          <SpecRow label="Material" value={String(specs?.material ?? "—")} />
          <SpecRow label="Norma" value={String(specs?.norma ?? "—")} />
          <SpecRow label="Tipo" value={String(specs?.valve_type ?? specs?.type ?? "—")} />
          <SpecRow label="PN" value={String(specs?.pn ?? "—")} />
          <SpecRow label="Rosca" value={String(specs?.thread ?? "—")} />
        </div>
      </div>

      {/* Precio + score */}
      <div className="flex w-28 shrink-0 flex-col items-end gap-1.5 pt-0.5">
        <div className="mt-mono text-[15px] font-bold tracking-[-0.2px]" style={{ color: MT.ink }}>
          {fmtAED(priceNum)}
        </div>
        <ScorePill score={score} size="lg" />
        {delivery_text && (
          <span className="text-right text-[10.5px] leading-tight" style={{ color: MT.ink3 }}>
            {delivery_text}
          </span>
        )}
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
        <a
          href={`https://www.amazon.ae/dp/${external_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-mono inline-flex h-5 items-center justify-center gap-1 text-[10px] hover:underline"
          style={{ color: MT.ink4 }}
        >
          <ExternalLink className="size-3" /> Amazon UAE
        </a>
      </div>
    </div>
  );
}
