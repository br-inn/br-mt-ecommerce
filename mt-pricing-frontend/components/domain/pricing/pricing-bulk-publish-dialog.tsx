"use client";

import * as React from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MtButton, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { useBulkPublish } from "@/lib/hooks/pricing/use-pricing-engine";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** IDs preseleccionados (resultados de la cola de aprobación). */
  priceIds: string[];
  /** Canal en común (label informativo). */
  channelLabel?: string | undefined;
  onPublished?: ((taskId: string) => void) | undefined;
}

/**
 * Diálogo de bulk-publish para enviar N propuestas approved a connector.
 *
 * UX:
 *  - Muestra cuenta total + canal.
 *  - Reason opcional.
 *  - Botón primario "Publicar (N)" en cobalt.
 *  - Al éxito retorna `task_id` al caller para polling de progreso.
 */
export function PricingBulkPublishDialog({
  open,
  onOpenChange,
  priceIds,
  channelLabel,
  onPublished,
}: Props) {
  const [reason, setReason] = React.useState("");
  const publish = useBulkPublish();

  const handleOpenChange = React.useCallback(
    (next: boolean) => {
      if (!next) setReason("");
      onOpenChange(next);
    },
    [onOpenChange],
  );

  const handlePublish = async () => {
    try {
      const res = await publish.mutateAsync({
        price_ids: priceIds,
        ...(channelLabel ? { channel_code: channelLabel } : {}),
        ...(reason ? { reason } : {}),
      });
      handleOpenChange(false);
      onPublished?.(res.task_id);
    } catch {
      /* toast el hook */
    }
  };

  const total = priceIds.length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Publicar propuestas</DialogTitle>
          <DialogDescription>
            Envía las propuestas seleccionadas al connector del canal.
            La acción es asíncrona y se monitoriza por job.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div
            className="rounded-md border p-3 text-[12.5px]"
            style={{ borderColor: MT.border, backgroundColor: MT.surface2 }}
          >
            <div className="flex items-center justify-between">
              <span style={{ color: MT.ink3 }}>Propuestas a publicar</span>
              <Pill tone="brand" mono>
                {total}
              </Pill>
            </div>
            {channelLabel ? (
              <div className="mt-2 flex items-center justify-between">
                <span style={{ color: MT.ink3 }}>Canal</span>
                <span className="mt-mono">{channelLabel}</span>
              </div>
            ) : null}
          </div>

          <label className="flex flex-col gap-1">
            <span
              className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
              style={{ color: MT.ink3 }}
            >
              Motivo (opcional)
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Lanzamiento campaña Ramadán 2026…"
              className="w-full resize-none rounded-[4px] border px-2 py-1.5 text-[13px]"
              style={{ borderColor: MT.border }}
              data-testid="bulk-publish-reason"
            />
          </label>
        </div>

        <DialogFooter className="gap-2">
          <MtButton
            tone="ghost"
            type="button"
            onClick={() => handleOpenChange(false)}
            disabled={publish.isPending}
          >
            Cancelar
          </MtButton>
          <MtButton
            tone="primary"
            type="button"
            onClick={handlePublish}
            disabled={publish.isPending || total === 0}
            data-testid="bulk-publish-submit"
          >
            {publish.isPending ? "Encolando…" : `Publicar (${total})`}
          </MtButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
