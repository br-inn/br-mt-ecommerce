"use client";

import * as React from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

interface DiscardReasonDialogProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onConfirm: (reason: string | undefined) => void;
}

export function DiscardReasonDialog({ open, onOpenChange, onConfirm }: DiscardReasonDialogProps) {
  const [reason, setReason] = React.useState("");

  React.useEffect(() => {
    if (open) setReason("");
  }, [open]);

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Descartar candidato"
      description="Indica el motivo del descarte (opcional). Ayuda a auditar el matching."
      confirmLabel="Descartar"
      destructive
      onConfirm={() => onConfirm(reason.trim() || undefined)}
    >
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={3}
        placeholder="Motivo (opcional)…"
        className="mt-2 w-full rounded-[6px] border p-2 text-[12px]"
      />
    </ConfirmDialog>
  );
}
