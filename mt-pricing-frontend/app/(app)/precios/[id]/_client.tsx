"use client";

/**
 * `/precios/[id]` — detalle de propuesta end-to-end (US-1B-01-06 S4).
 *
 * Reescritura del placeholder S2/S3:
 *  - `PricingDetailCard` con amounts + breakdown estructurado.
 *  - `PricingAlertsPanel` con drill-down por severidad.
 *  - History timeline reusando primitives MT.
 *  - Acciones: approve / reject / revise (vía dialog) / bulk-publish (1-pack).
 *  - Polling de progreso si se lanza un job tras revise/publish.
 */

import * as React from "react";
import { CheckCircle2, ScrollText, Send, X } from "lucide-react";
import { toast } from "sonner";

import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { PricingAlertsPanel } from "@/components/domain/pricing/pricing-alerts-panel";
import { PricingDetailCard } from "@/components/domain/pricing/pricing-detail-card";
import { PricingReviseDialog } from "@/components/domain/pricing/pricing-revise-dialog";
import { PricingBulkPublishDialog } from "@/components/domain/pricing/pricing-bulk-publish-dialog";
import {
  useApprovePrice,
  usePriceDetail,
  useRejectPrice,
} from "@/lib/hooks/pricing/use-pricing";
import { useTaskProgress } from "@/lib/hooks/pricing/use-pricing-engine";
import type { PriceStatus } from "@/lib/api/endpoints/pricing";
import type { ProgressEvent } from "@/lib/api/endpoints/pricing-engine";

const TERMINAL: ReadonlySet<PriceStatus> = new Set([
  "exported",
  "rejected",
  "superseded",
]);

interface Props {
  id: string;
}

export function PriceDetailClient({ id }: Props) {
  const { data: price, isLoading, isError, refetch } = usePriceDetail(id);
  const [reviseOpen, setReviseOpen] = React.useState(false);
  const [publishOpen, setPublishOpen] = React.useState(false);
  const [taskId, setTaskId] = React.useState<string | null>(null);

  const approve = useApprovePrice();
  const reject = useRejectPrice();
  const [rejectReason, setRejectReason] = React.useState("");

  const progress = useTaskProgress(taskId ?? undefined, !!taskId);

  // Cuando el job termina, dejamos de polling y refrescamos el detalle.
  React.useEffect(() => {
    if (!progress.data) return;
    if (
      progress.data.status === "success" ||
      progress.data.status === "failed"
    ) {
      void refetch();
    }
  }, [progress.data, refetch]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <MtSkeleton width="40%" height={32} />
        <MtSkeleton width="100%" height={120} />
        <MtSkeleton width="100%" height={80} />
      </div>
    );
  }

  if (isError || !price) {
    return (
      <MtError
        message="No se pudo cargar la propuesta."
        onRetry={() => void refetch()}
      />
    );
  }

  const isTerminal = TERMINAL.has(price.status);
  const canPublish =
    price.status === "approved" || price.status === "auto_approved";

  const handleApprove = async () => {
    try {
      await approve.mutateAsync({ id });
    } catch {
      /* el hook ya muestra toast */
    }
  };

  const handleReject = async () => {
    if (!rejectReason || rejectReason.length < 8) {
      toast.error("Indica un motivo (≥ 8 caracteres) para rechazar.");
      return;
    }
    try {
      await reject.mutateAsync({ id, reason: rejectReason });
      setRejectReason("");
    } catch {
      /* hook toast */
    }
  };

  return (
    <div className="space-y-6">
      <PricingDetailCard price={price} />

      <PricingAlertsPanel alerts={price.alerts} />

      <SectionCard
        title="Historial de aprobación"
        subtitle={`${price.approval_events.length} evento(s)`}
      >
        {price.approval_events.length === 0 ? (
          <div
            className="px-4 py-6 text-center text-[12.5px]"
            style={{ color: MT.ink3 }}
          >
            Sin eventos en el historial.
          </div>
        ) : (
          <ol
            className="divide-y"
            style={{ borderColor: MT.border }}
          >
            {price.approval_events.map((evt) => (
              <li key={evt.id} className="px-4 py-3 text-[12.5px]">
                <div className="flex flex-wrap items-center gap-2">
                  <ScrollText
                    className="size-3.5"
                    style={{ color: MT.ink4 }}
                  />
                  <span
                    className="mt-mono text-[11px]"
                    style={{ color: MT.ink3 }}
                  >
                    {new Date(evt.created_at).toLocaleString()}
                  </span>
                  <Pill tone="neutral" mono>
                    {evt.from_status} → {evt.to_status}
                  </Pill>
                </div>
                {evt.reason ? (
                  <p
                    className="mt-1 italic"
                    style={{ color: MT.ink3 }}
                  >
                    “{evt.reason}”
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        )}
      </SectionCard>

      {taskId ? (
        <SectionCard
          title="Progreso del job"
          subtitle={`task ${taskId.slice(0, 12)}`}
          actions={
            progress.data ? (
              <Pill
                tone={
                  progress.data.status === "success"
                    ? "success"
                    : progress.data.status === "failed"
                      ? "danger"
                      : "warning"
                }
                dot
              >
                {progress.data.status}
              </Pill>
            ) : null
          }
        >
          <div className="px-4 py-3 text-[12.5px]">
            {progress.isLoading || !progress.data ? (
              <MtSkeleton width="100%" height={24} />
            ) : (
              <ProgressBar event={progress.data} />
            )}
          </div>
        </SectionCard>
      ) : null}

      {!isTerminal ? (
        <SectionCard title="Acciones">
          <div className="flex flex-col gap-3 px-4 py-3">
            <div className="flex flex-wrap gap-2">
              <MtButton
                tone="primary"
                onClick={handleApprove}
                disabled={approve.isPending || price.status === "approved"}
                icon={<CheckCircle2 className="size-3.5" />}
              >
                Aprobar
              </MtButton>
              <MtButton
                tone="neutral"
                onClick={() => setReviseOpen(true)}
                disabled={approve.isPending || reject.isPending}
              >
                Revisar
              </MtButton>
              {canPublish ? (
                <MtButton
                  tone="primary"
                  onClick={() => setPublishOpen(true)}
                  icon={<Send className="size-3.5" />}
                >
                  Publicar
                </MtButton>
              ) : null}
            </div>

            <div className="rounded-md border p-3" style={{ borderColor: MT.border }}>
              <label className="flex flex-col gap-1">
                <span
                  className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
                  style={{ color: MT.ink3 }}
                >
                  Rechazo (mínimo 8 caracteres)
                </span>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={2}
                  placeholder="Margen insuficiente para canal pre_launch…"
                  className="w-full resize-none rounded-[4px] border px-2 py-1.5 text-[13px]"
                  style={{ borderColor: MT.border }}
                />
              </label>
              <div className="mt-2 flex justify-end">
                <MtButton
                  tone="danger"
                  size="sm"
                  onClick={handleReject}
                  disabled={
                    reject.isPending ||
                    rejectReason.length < 8
                  }
                  icon={<X className="size-3.5" />}
                >
                  Rechazar
                </MtButton>
              </div>
            </div>
          </div>
        </SectionCard>
      ) : null}

      <PricingReviseDialog
        open={reviseOpen}
        onOpenChange={setReviseOpen}
        priceId={id}
        currentAmount={price.amount}
        currency={price.currency}
        onSuccess={() => void refetch()}
      />

      <PricingBulkPublishDialog
        open={publishOpen}
        onOpenChange={setPublishOpen}
        priceIds={[id]}
        onPublished={(t) => {
          setTaskId(t);
          toast.success("Job de publicación lanzado");
        }}
      />
    </div>
  );
}

function ProgressBar({
  event,
}: {
  event: ProgressEvent;
}) {
  const pct =
    event.total > 0
      ? Math.min(100, Math.round((event.processed / event.total) * 100))
      : 0;
  return (
    <div className="space-y-2">
      <div
        className="h-2 w-full overflow-hidden rounded-full border"
        style={{ borderColor: MT.border, backgroundColor: MT.surface3 }}
      >
        <div
          className="h-full"
          style={{
            width: `${pct}%`,
            backgroundColor:
              event.status === "failed" ? MT.danger : MT.brand,
            transition: "width 0.3s ease-out",
          }}
        />
      </div>
      <div
        className="flex items-center justify-between text-[11.5px] mt-mono mt-tnum"
        style={{ color: MT.ink3 }}
      >
        <span>
          {event.processed}/{event.total} ({pct}%)
        </span>
        {event.eta_seconds !== null ? (
          <span>ETA {event.eta_seconds}s</span>
        ) : (
          <span>—</span>
        )}
      </div>
      {event.failed > 0 ? (
        <div className="text-[11.5px]" style={{ color: MT.danger }}>
          {event.failed} fallidos
        </div>
      ) : null}
    </div>
  );
}

export default PriceDetailClient;
