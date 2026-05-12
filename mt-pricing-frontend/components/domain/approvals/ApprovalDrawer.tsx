"use client";

/**
 * ApprovalDrawer — drawer lateral con detalle completo del precio
 * y acciones Aprobar / Rechazar / Revisar.
 *
 * US-1B-02-06 · Pantalla 14 "Cola de aprobación"
 */

import * as React from "react";
import { toast } from "sonner";

import { MtButton, Pill } from "@/components/mt/primitives";
import { MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { useApprovalDetail, useApproveOne, useRejectOne, useReviseOne } from "@/lib/hooks/approvals/use-approval-queue";
import type { PriceRow, PriceStatus } from "@/lib/api/endpoints/approvals";

// ---- Status labels/tones ---------------------------------------------------

const STATUS_TONE: Record<PriceStatus, "success" | "warning" | "danger" | "neutral" | "brand"> = {
  draft: "neutral",
  pending_review: "warning",
  auto_approved: "brand",
  approved: "success",
  rejected: "danger",
  revised: "warning",
  exported: "brand",
  superseded: "neutral",
  migrated: "neutral",
};

const STATUS_LABEL: Record<PriceStatus, string> = {
  draft: "Borrador",
  pending_review: "Pendiente",
  auto_approved: "Auto-aprobado",
  approved: "Aprobado",
  rejected: "Rechazado",
  revised: "Revisado",
  exported: "Exportado",
  superseded: "Reemplazado",
  migrated: "Migrado",
};

// ---- Types -----------------------------------------------------------------

type DrawerAction = "approve" | "reject" | "revise" | null;

interface Props {
  priceId: string | null;
  canWrite: boolean;
  onClose: () => void;
  onActionDone?: () => void;
}

// ---- KV Row helper ---------------------------------------------------------

function KvRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2 py-1.5 border-b last:border-b-0" style={{ borderColor: MT.border }}>
      <span className="mt-mono text-[10.5px] uppercase tracking-[0.5px] shrink-0" style={{ color: MT.ink3 }}>
        {label}
      </span>
      <span className="text-[13px] text-right" style={{ color: MT.ink }}>
        {children}
      </span>
    </div>
  );
}

// ---- Action panel ----------------------------------------------------------

interface ActionPanelProps {
  priceId: string;
  canWrite: boolean;
  onDone: () => void;
}

function ActionPanel({ priceId, canWrite, onDone }: ActionPanelProps) {
  const [activeAction, setActiveAction] = React.useState<DrawerAction>(null);
  const [comment, setComment] = React.useState("");
  const [newAmount, setNewAmount] = React.useState("");

  const approve = useApproveOne();
  const reject = useRejectOne();
  const revise = useReviseOne();

  const isPending = approve.isPending || reject.isPending || revise.isPending;

  const commentError =
    activeAction === "reject" && comment.length > 0 && comment.length < 10
      ? "Mínimo 10 caracteres"
      : undefined;

  const canSubmit =
    !isPending &&
    comment.length >= (activeAction === "revise" ? 1 : 10) &&
    (activeAction !== "revise" || newAmount.length > 0);

  const handleSubmit = async () => {
    try {
      if (activeAction === "approve") {
        const reason = comment || undefined;
        await approve.mutateAsync({ id: priceId, ...(reason !== undefined ? { reason } : {}) });
      } else if (activeAction === "reject") {
        if (comment.length < 10) {
          toast.error("El comentario debe tener al menos 10 caracteres");
          return;
        }
        await reject.mutateAsync({ id: priceId, reason: comment });
      } else if (activeAction === "revise") {
        await revise.mutateAsync({ id: priceId, newAmount, reason: comment });
      }
      setActiveAction(null);
      setComment("");
      setNewAmount("");
      onDone();
    } catch {
      /* toast lanzado por el hook */
    }
  };

  if (!canWrite) {
    return (
      <p className="text-xs" style={{ color: MT.ink3 }}>
        Solo lectura — sin permiso de aprobación.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Botones de acción */}
      <div className="flex gap-2">
        <MtButton
          tone="primary"
          size="sm"
          disabled={isPending}
          onClick={() => setActiveAction(activeAction === "approve" ? null : "approve")}
        >
          Aprobar
        </MtButton>
        <MtButton
          tone="danger"
          size="sm"
          disabled={isPending}
          onClick={() => setActiveAction(activeAction === "reject" ? null : "reject")}
        >
          Rechazar
        </MtButton>
        <MtButton
          tone="neutral"
          size="sm"
          disabled={isPending}
          onClick={() => setActiveAction(activeAction === "revise" ? null : "revise")}
        >
          Revisar
        </MtButton>
      </div>

      {/* Panel expandible según acción */}
      {activeAction !== null && (
        <div
          className="rounded-[6px] border p-3 space-y-3"
          style={{ borderColor: MT.border, background: MT.surface2 }}
        >
          <p className="mt-mono text-[10.5px] uppercase tracking-[0.5px]" style={{ color: MT.ink3 }}>
            {activeAction === "approve" && "Confirmar aprobación"}
            {activeAction === "reject" && "Rechazar — razón obligatoria"}
            {activeAction === "revise" && "Proponer nuevo importe"}
          </p>

          {activeAction === "revise" && (
            <div className="flex flex-col gap-1">
              <label
                className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
                style={{ color: MT.ink3 }}
              >
                Nuevo importe
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={newAmount}
                onChange={(e) => setNewAmount(e.target.value)}
                placeholder="145.99"
                className="w-full rounded-[4px] border px-2 py-1.5 text-[13px] mt-mono"
                style={{ borderColor: MT.border }}
              />
            </div>
          )}

          <div className="flex flex-col gap-1">
            <label
              className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
              style={{ color: MT.ink3 }}
            >
              {activeAction === "approve" ? "Comentario (opcional)" : "Comentario (≥10 chars)"}
            </label>
            <textarea
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={
                activeAction === "approve"
                  ? "Justificación opcional…"
                  : activeAction === "reject"
                    ? "Motivo del rechazo…"
                    : "Motivo del ajuste…"
              }
              className="w-full resize-none rounded-[4px] border px-2 py-1.5 text-[13px]"
              style={{ borderColor: commentError ? MT.danger : MT.border }}
            />
            {commentError ? (
              <span className="text-[11.5px]" style={{ color: MT.danger }}>
                {commentError}
              </span>
            ) : null}
          </div>

          <div className="flex gap-2 justify-end">
            <MtButton
              tone="ghost"
              size="sm"
              onClick={() => {
                setActiveAction(null);
                setComment("");
                setNewAmount("");
              }}
            >
              Cancelar
            </MtButton>
            <MtButton
              tone={activeAction === "reject" ? "danger" : "primary"}
              size="sm"
              disabled={!canSubmit}
              onClick={() => void handleSubmit()}
            >
              {isPending
                ? "Guardando…"
                : activeAction === "approve"
                  ? "Confirmar aprobación"
                  : activeAction === "reject"
                    ? "Confirmar rechazo"
                    : "Enviar revisión"}
            </MtButton>
          </div>
        </div>
      )}
    </div>
  );
}

// ---- Main drawer -----------------------------------------------------------

export function ApprovalDrawer({ priceId, canWrite, onClose, onActionDone }: Props) {
  const { data: price, isLoading } = useApprovalDetail(priceId ?? undefined);

  const breakdownEntries = price?.breakdown ? Object.entries(price.breakdown) : [];

  return (
    <Sheet open={!!priceId} onOpenChange={(open) => { if (!open) onClose(); }}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[520px] overflow-y-auto flex flex-col gap-0 p-0"
      >
        <SheetHeader className="px-5 py-4 border-b" style={{ borderColor: MT.border }}>
          <SheetTitle className="flex items-center gap-2 flex-wrap">
            {isLoading ? (
              <MtSkeleton width={180} height={18} />
            ) : price ? (
              <>
                <span className="mt-mono text-[15px]">{price.product_sku}</span>
                <span style={{ color: MT.ink4 }}>·</span>
                <span className="mt-mono text-[12px]" style={{ color: MT.ink3 }}>
                  {price.scheme_code}
                </span>
                <Pill tone={STATUS_TONE[price.status]} dot>
                  {STATUS_LABEL[price.status]}
                </Pill>
              </>
            ) : (
              "Detalle de precio"
            )}
          </SheetTitle>
          {price && (
            <SheetDescription>
              Canal {price.channel_id} · creado{" "}
              {new Date(price.created_at).toLocaleString("es-ES")}
            </SheetDescription>
          )}
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <MtSkeleton key={i} width="100%" height={28} />
              ))}
            </div>
          ) : price ? (
            <>
              {/* Importes */}
              <section>
                <p
                  className="mt-mono text-[10.5px] uppercase tracking-[0.5px] mb-2"
                  style={{ color: MT.ink3 }}
                >
                  Importes
                </p>
                <div
                  className="rounded-[6px] border divide-y"
                  style={{ borderColor: MT.border }}
                >
                  <KvRow label="Precio propuesto">
                    <span className="mt-mono mt-tnum text-[16px] font-semibold">
                      {price.amount}{" "}
                      <span className="text-[11px] font-normal" style={{ color: MT.ink3 }}>
                        {price.currency}
                      </span>
                    </span>
                  </KvRow>
                  <KvRow label="PVP mínimo">
                    <span className="mt-mono mt-tnum">{price.pvp_min ?? "—"}</span>
                  </KvRow>
                  <KvRow label="Margen">
                    <span className="mt-mono mt-tnum">
                      {(Number(price.margin_pct) * 100).toFixed(2)}%
                    </span>
                  </KvRow>
                  <KvRow label="Regla aplicada">
                    <span className="mt-mono text-[12px]">{price.rule_applied ?? "—"}</span>
                  </KvRow>
                  <KvRow label="Fórmula">
                    <code className="mt-mono text-[11px] break-all" style={{ color: MT.ink2 }}>
                      {price.formula ?? "—"}
                    </code>
                  </KvRow>
                </div>
              </section>

              {/* Alertas */}
              {price.alerts.length > 0 && (
                <section>
                  <p
                    className="mt-mono text-[10.5px] uppercase tracking-[0.5px] mb-2"
                    style={{ color: MT.ink3 }}
                  >
                    Alertas ({price.alerts.length})
                  </p>
                  <div className="space-y-1.5">
                    {price.alerts.map((alert, i) => (
                      <div
                        key={i}
                        className="rounded-[5px] border px-3 py-2 text-[12px]"
                        style={{
                          borderColor:
                            alert.severity === "critical"
                              ? MT.dangerBorder
                              : alert.severity === "warning"
                                ? MT.warningBorder
                                : MT.border,
                          background:
                            alert.severity === "critical"
                              ? MT.dangerSoft
                              : alert.severity === "warning"
                                ? MT.warningSoft
                                : MT.surface2,
                          color:
                            alert.severity === "critical"
                              ? MT.danger
                              : alert.severity === "warning"
                                ? MT.warning
                                : MT.ink,
                        }}
                      >
                        <span className="font-medium mt-mono">[{alert.code}]</span>{" "}
                        {alert.message}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Breakdown */}
              {breakdownEntries.length > 0 && (
                <section>
                  <p
                    className="mt-mono text-[10.5px] uppercase tracking-[0.5px] mb-2"
                    style={{ color: MT.ink3 }}
                  >
                    Breakdown ({breakdownEntries.length})
                  </p>
                  <div
                    className="rounded-[6px] border divide-y overflow-x-auto"
                    style={{ borderColor: MT.border }}
                  >
                    {breakdownEntries.map(([key, val]) => (
                      <KvRow key={key} label={key}>
                        <span className="mt-mono text-[12px]">
                          {val === null || typeof val !== "object"
                            ? String(val)
                            : JSON.stringify(val)}
                        </span>
                      </KvRow>
                    ))}
                  </div>
                </section>
              )}

              {/* Historial de eventos */}
              {"approval_events" in price && Array.isArray(price.approval_events) && price.approval_events.length > 0 && (
                <section>
                  <p
                    className="mt-mono text-[10.5px] uppercase tracking-[0.5px] mb-2"
                    style={{ color: MT.ink3 }}
                  >
                    Historial ({price.approval_events.length})
                  </p>
                  <ol className="space-y-1.5">
                    {price.approval_events.map((ev) => (
                      <li
                        key={ev.id}
                        className="rounded-[5px] border px-3 py-2 text-[12px] flex items-start gap-2"
                        style={{ borderColor: MT.border, background: MT.surface2 }}
                      >
                        <Pill tone={STATUS_TONE[ev.to_status] ?? "neutral"} dot>
                          {STATUS_LABEL[ev.to_status] ?? ev.to_status}
                        </Pill>
                        <div className="flex-1 min-w-0">
                          {ev.reason && (
                            <p style={{ color: MT.ink2 }}>{ev.reason}</p>
                          )}
                          <p className="mt-mono text-[11px]" style={{ color: MT.ink3 }}>
                            {new Date(ev.created_at).toLocaleString("es-ES")}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>
              )}
            </>
          ) : null}
        </div>

        {/* Acciones */}
        {price && (
          <div
            className="px-5 py-4 border-t"
            style={{ borderColor: MT.border, background: MT.surface }}
          >
            <ActionPanel
              priceId={price.id}
              canWrite={canWrite}
              onDone={() => {
                onActionDone?.();
                onClose();
              }}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
