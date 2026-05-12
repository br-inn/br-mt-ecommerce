"use client";

/**
 * BulkActionBar — barra sticky que aparece cuando hay ≥1 precio seleccionado.
 *
 * Acciones:
 *  - Aprobar (n)           → POST /prices/bulk-approve (comment obligatorio)
 *  - Rechazar (n)          → POST individual por cada ID + comentario
 *  - Limpiar selección
 *
 * Validaciones:
 *  - comment ≥ 10 chars siempre para bulk-approve
 *  - bulk > 50 items bloquea hasta tener comentario
 *
 * US-1B-02-06 · Pantalla 14
 */

import * as React from "react";
import { toast } from "sonner";

import { MtButton } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { useBulkApprove, useRejectOne } from "@/lib/hooks/approvals/use-approval-queue";

interface Props {
  selectedIds: string[];
  onClearSelection: () => void;
  onBulkActionDone?: () => void;
}

type BulkMode = "approve" | "reject" | null;

export function BulkActionBar({ selectedIds, onClearSelection, onBulkActionDone }: Props) {
  const [mode, setMode] = React.useState<BulkMode>(null);
  const [comment, setComment] = React.useState("");

  const bulkApprove = useBulkApprove();
  const rejectOne = useRejectOne();

  const n = selectedIds.length;

  // Validaciones
  const commentError =
    comment.length > 0 && comment.length < 10 ? "Mínimo 10 caracteres" : undefined;
  const needsComment = mode === "approve" || mode === "reject";
  const canSubmit =
    !bulkApprove.isPending &&
    !rejectOne.isPending &&
    needsComment &&
    comment.length >= 10;

  const handleOpenChange = (next: BulkMode) => {
    setMode((prev) => (prev === next ? null : next));
    setComment("");
  };

  const handleApprove = async () => {
    if (comment.length < 10) {
      toast.error("Comentario obligatorio (≥10 chars)");
      return;
    }
    try {
      await bulkApprove.mutateAsync({ ids: selectedIds, comment });
      setMode(null);
      setComment("");
      onClearSelection();
      onBulkActionDone?.();
    } catch {
      /* toast lanzado por el hook */
    }
  };

  const handleRejectAll = async () => {
    if (comment.length < 10) {
      toast.error("Comentario obligatorio (≥10 chars)");
      return;
    }
    try {
      // Rechaza en secuencia (evita saturar el backend)
      let rejected = 0;
      for (const id of selectedIds) {
        try {
          await rejectOne.mutateAsync({ id, reason: comment });
          rejected++;
        } catch {
          /* toast individual ya lanzado */
        }
      }
      if (rejected > 0) toast.success(`${rejected} precio${rejected !== 1 ? "s" : ""} rechazado${rejected !== 1 ? "s" : ""}`);
      setMode(null);
      setComment("");
      onClearSelection();
      onBulkActionDone?.();
    } catch {
      /* noop */
    }
  };

  if (n === 0) return null;

  return (
    <div
      className="fixed bottom-0 inset-x-0 z-40 border-t shadow-lg flex flex-col gap-0"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      {/* Barra principal */}
      <div className="flex items-center gap-3 px-6 py-3 flex-wrap">
        <span
          className="mt-mono text-[12px] font-medium shrink-0"
          style={{ color: MT.ink }}
        >
          {n} seleccionado{n !== 1 ? "s" : ""}
        </span>

        <div className="flex items-center gap-2 flex-wrap">
          <MtButton
            tone="primary"
            size="sm"
            disabled={bulkApprove.isPending || rejectOne.isPending}
            onClick={() => handleOpenChange("approve")}
          >
            Aprobar ({n})
          </MtButton>

          <MtButton
            tone="danger"
            size="sm"
            disabled={bulkApprove.isPending || rejectOne.isPending}
            onClick={() => handleOpenChange("reject")}
          >
            Rechazar ({n}) con comentario
          </MtButton>

          <MtButton
            tone="ghost"
            size="sm"
            onClick={() => {
              setMode(null);
              setComment("");
              onClearSelection();
            }}
          >
            Limpiar selección
          </MtButton>
        </div>

        {n > 50 && (
          <span className="text-[11.5px]" style={{ color: MT.warning }}>
            Bulk &gt;50 — comentario obligatorio
          </span>
        )}
      </div>

      {/* Panel de comentario expandible */}
      {mode !== null && (
        <div
          className="px-6 pb-4 pt-0 border-t flex flex-col gap-2"
          style={{ borderColor: MT.border }}
        >
          <label
            className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
            style={{ color: MT.ink3 }}
          >
            {mode === "approve" ? "Comentario aprobación (≥10 chars)" : "Motivo rechazo (≥10 chars)"}
          </label>
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={
              mode === "approve"
                ? "Aprobación en lote — justificación…"
                : "Motivo del rechazo masivo…"
            }
            className="w-full resize-none rounded-[4px] border px-2 py-1.5 text-[13px]"
            style={{ borderColor: commentError ? MT.danger : MT.border }}
          />
          {commentError && (
            <span className="text-[11.5px]" style={{ color: MT.danger }}>
              {commentError}
            </span>
          )}
          <div className="flex gap-2 justify-end">
            <MtButton
              tone="ghost"
              size="sm"
              onClick={() => {
                setMode(null);
                setComment("");
              }}
            >
              Cancelar
            </MtButton>
            <MtButton
              tone={mode === "reject" ? "danger" : "primary"}
              size="sm"
              disabled={!canSubmit}
              onClick={() => void (mode === "approve" ? handleApprove() : handleRejectAll())}
            >
              {bulkApprove.isPending || rejectOne.isPending
                ? "Procesando…"
                : mode === "approve"
                  ? `Aprobar ${n} precio${n !== 1 ? "s" : ""}`
                  : `Rechazar ${n} precio${n !== 1 ? "s" : ""}`}
            </MtButton>
          </div>
        </div>
      )}
    </div>
  );
}
