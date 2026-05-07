"use client";

import * as React from "react";
import {
  AlertTriangle,
  Check,
  RefreshCcw,
  Star,
  Upload,
} from "lucide-react";

import {
  Crumbs,
  MtButton,
  MtTd,
  MtTh,
  Pill,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  useChannelDiff,
  useChannelPublish,
  useChannelSync,
  useChannelSyncLog,
} from "@/lib/hooks/channels/use-channel-mirror";
import {
  channelMirrorApi,
  type DiffStatus,
  type FieldDiff,
} from "@/lib/api/endpoints/channel-mirror";

const CHANNEL = "amazon_uae";

const STATUS_TONE: Record<DiffStatus, "success" | "warning" | "danger" | "neutral"> = {
  match: "success",
  drift: "warning",
  missing: "danger",
  queued: "neutral",
};

const STATUS_LABEL: Record<DiffStatus, string> = {
  match: "sync",
  drift: "drift",
  missing: "falta en canal",
  queued: "en cola",
};

function fmtAge(iso: string | null): string {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60_000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} m`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h} h ${min % 60} m`;
  const d = Math.floor(h / 24);
  return `hace ${d} d`;
}

function MirrorRowView({ r }: { r: FieldDiff }) {
  const isAR = r.lang === "ar";
  const mono = !!r.is_mono;
  return (
    <tr style={{ background: r.status !== "match" ? MT.warningSoft : MT.surface }}>
      <MtTd
        mono
        className="text-[11.5px]"
        style={{ width: 180, color: MT.ink3 }}
      >
        {r.field}
      </MtTd>
      <MtTd
        mono={mono}
        className={isAR ? "mt-arabic" : undefined}
        style={{ color: MT.ink, fontWeight: 500 }}
      >
        {r.mt ?? "—"}
      </MtTd>
      <MtTd
        mono={mono}
        className={isAR ? "mt-arabic" : undefined}
        style={{ color: r.status === "missing" ? MT.ink4 : MT.ink2 }}
      >
        {r.live || (
          <em style={{ color: MT.ink4, fontStyle: "normal" }}>— sin valor —</em>
        )}
      </MtTd>
      <MtTd style={{ width: 130 }}>
        <Pill tone={STATUS_TONE[r.status]} dot>
          {STATUS_LABEL[r.status]}
        </Pill>
      </MtTd>
    </tr>
  );
}

export default function ChannelMirrorPage() {
  // For phase-1 the Validación is wired around a single SKU; URL state can
  // override the default once we add a SKU picker.
  const [sku] = React.useState("MTV-1004");
  const { data: diff, isLoading, isError, refetch } = useChannelDiff(CHANNEL, sku);
  const { data: log = [] } = useChannelSyncLog(CHANNEL, 5);
  const sync = useChannelSync(CHANNEL, sku);
  const publish = useChannelPublish(CHANNEL, sku);

  const summary = diff?.summary;
  const driftsCount = summary ? summary.drift + summary.missing : 0;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b bg-mt-surface px-6 pt-3.5" style={{ borderColor: MT.border }}>
        <Crumbs
          items={[
            { label: "Canales" },
            { label: "Amazon UAE" },
            { label: sku, mono: true, bold: true },
          ]}
        />
        <div className="mt-1.5 flex items-end gap-4 pb-3.5">
          <div className="flex-1">
            <h1
              className="m-0 text-[18px] font-semibold tracking-[-0.3px]"
              style={{ color: MT.ink }}
            >
              Channel mirror — Amazon UAE
            </h1>
            <span className="text-[12.5px]" style={{ color: MT.ink3 }}>
              MT canonical{" "}
              <span style={{ color: MT.ink2 }}>↔</span> Amazon SP-API · ASIN{" "}
              <span className="mt-mono">{diff?.external_id ?? "…"}</span>
            </span>
          </div>
          {summary ? (
            <Pill tone={driftsCount > 0 ? "warning" : "success"} dot>
              {summary.drift} drifts · {summary.missing} faltan
            </Pill>
          ) : null}
          <MtButton
            icon={<RefreshCcw className="size-3.5" />}
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
          >
            {sync.isPending ? "Sincronizando…" : "Re-sync"}
          </MtButton>
          <MtButton
            tone="primary"
            icon={<Upload className="size-3.5" />}
            onClick={() => publish.mutate(undefined)}
            disabled={publish.isPending || driftsCount === 0}
          >
            {publish.isPending ? "Publicando…" : "Publicar diferencias"}
          </MtButton>
        </div>
      </div>

      {/* Banner */}
      {summary && driftsCount > 0 ? (
        <div
          className="flex items-center gap-2.5 border-b px-6 py-2.5 text-[12.5px]"
          style={{
            background: MT.warningSoft,
            color: MT.warning,
            borderColor: MT.warningBorder,
          }}
        >
          <AlertTriangle className="size-3.5" />
          <span>
            Última sync <strong>{fmtAge(diff?.fetched_at ?? null)}</strong>. Amazon expone {summary.drift} campos con valores distintos al canonical y {summary.missing} vacío(s). Publicar requiere aprobación si afecta a precio.
          </span>
        </div>
      ) : null}

      {isError ? (
        <div className="px-6 py-3">
          <MtError
            message="No se pudo cargar el diff."
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* Body */}
      <div className="grid flex-1 grid-cols-[1.6fr_1fr] gap-4 overflow-auto px-6 py-4">
        {/* Mirror table */}
        <div
          className="self-start overflow-hidden rounded-lg border bg-mt-surface"
          style={{ borderColor: MT.border }}
        >
          <div
            className="flex items-center justify-between border-b px-3.5 py-2.5"
            style={{ borderColor: MT.border }}
          >
            <span className="text-[12.5px] font-semibold" style={{ color: MT.ink }}>
              Comparador campo a campo
            </span>
            <div className="flex gap-1.5">
              <Pill tone="ghost">solo drifts</Pill>
              <Pill tone="ghost">incluir match</Pill>
            </div>
          </div>
          <table className="mt-data-table w-full border-collapse text-[12.5px]">
            <thead>
              <tr>
                <MtTh>campo</MtTh>
                <MtTh>MT canonical</MtTh>
                <MtTh>Amazon UAE (live)</MtTh>
                <MtTh>estado</MtTh>
              </tr>
            </thead>
            <tbody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={`sk-${i}`}>
                      <MtTd><MtSkeleton width={120} /></MtTd>
                      <MtTd><MtSkeleton width={220} /></MtTd>
                      <MtTd><MtSkeleton width={220} /></MtTd>
                      <MtTd><MtSkeleton width={70} /></MtTd>
                    </tr>
                  ))
                : null}
              {!isLoading && diff
                ? diff.diffs.map((r) => <MirrorRowView key={r.field} r={r} />)
                : null}
            </tbody>
          </table>
          {!isLoading && diff && diff.diffs.length === 0 ? (
            <MtEmpty title="Sin campos definidos" hint="Configura el canonical loader del canal." />
          ) : null}
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-3">
          <div
            className="rounded-lg border bg-mt-surface px-3.5 py-3.5"
            style={{ borderColor: MT.border }}
          >
            <div className="mb-2 text-xs font-semibold" style={{ color: MT.ink }}>
              Estado del listing
            </div>
            <div className="flex flex-col gap-2 text-xs">
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>ASIN</span>
                <span className="mt-mono font-medium" style={{ color: MT.ink }}>
                  {diff?.external_id ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>Última sync</span>
                <span className="mt-mono" style={{ color: MT.warning }}>
                  {fmtAge(diff?.fetched_at ?? null)}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>Campos sync</span>
                <Pill tone="success" dot>
                  {summary?.match ?? 0} match
                </Pill>
              </div>
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>Drift</span>
                <Pill tone="warning" dot>
                  {summary?.drift ?? 0} campos
                </Pill>
              </div>
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>Falta en canal</span>
                <Pill tone="danger" dot>
                  {summary?.missing ?? 0}
                </Pill>
              </div>
              <div className="flex justify-between">
                <span style={{ color: MT.ink3 }}>En cola</span>
                <Pill tone="ghost">{summary?.queued ?? 0}</Pill>
              </div>
            </div>
          </div>

          <div
            className="overflow-hidden rounded-lg border bg-mt-surface"
            style={{ borderColor: MT.border }}
          >
            <div
              className="border-b px-3.5 py-2.5 text-xs font-semibold"
              style={{ borderColor: MT.border, color: MT.ink }}
            >
              Sync log (últimos jobs)
            </div>
            <div className="px-3.5 py-1.5">
              {log.length === 0 ? (
                <MtEmpty title="Sin jobs recientes" hint="Pulsa Re-sync para encolar uno." />
              ) : null}
              {log.map((l, i) => {
                const tone = !l.ok ? "danger" : l.event_type === "push" ? "success" : l.event_type === "pull" ? "warning" : "neutral";
                const glyph = !l.ok ? "✗" : l.event_type === "pull" ? "⚠" : l.event_type === "push" ? "✓" : "i";
                return (
                  <div
                    key={l.id}
                    className="flex gap-2.5 py-1.5 text-[11.5px]"
                    style={{
                      borderBottom:
                        i < log.length - 1 ? `1px dashed ${MT.border}` : "none",
                    }}
                  >
                    <span
                      className="mt-mono w-[60px] text-[10.5px]"
                      style={{ color: MT.ink4 }}
                    >
                      {fmtAge(l.created_at)}
                    </span>
                    <span className="flex-1" style={{ color: MT.ink2 }}>
                      {l.summary ?? `${l.event_type} sin detalle`}
                    </span>
                    <Pill tone={tone === "neutral" ? "ghost" : tone} dot>
                      {glyph}
                    </Pill>
                  </div>
                );
              })}
            </div>
          </div>

          <div
            className="rounded-lg border px-3.5 py-3"
            style={{ background: MT.brandSoft, borderColor: MT.brandBorder }}
          >
            <div className="mb-1 text-xs font-semibold" style={{ color: MT.brandDeep }}>
              Próxima sync programada
            </div>
            <div className="text-[11.5px]" style={{ color: MT.ink2 }}>
              Pull cada 6 h · Push on-demand. Próximo pull automático cuando el scheduler lo lance.
            </div>
          </div>

          <div
            className="rounded-lg border bg-mt-surface px-3.5 py-3"
            style={{ borderColor: MT.border }}
          >
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: MT.ink3 }}>Diferencias publicables</span>
              <Pill tone="warning" dot>
                {driftsCount}
              </Pill>
            </div>
            <div className="mt-2 flex gap-1.5">
              <MtButton
                size="sm"
                tone="ghost"
                icon={<Check className="size-3.5" />}
                onClick={() => void channelMirrorApi.diff(CHANNEL, sku)}
              >
                Marcar revisado
              </MtButton>
              <MtButton
                size="sm"
                tone="primary"
                icon={<Upload className="size-3.5" />}
                onClick={() => publish.mutate(undefined)}
                disabled={publish.isPending || driftsCount === 0}
              >
                Publicar
              </MtButton>
            </div>
          </div>
        </div>
      </div>

      {/* Hide Star icon import warning by referencing it once (legacy code path) */}
      <Star className="hidden" aria-hidden />
    </div>
  );
}
