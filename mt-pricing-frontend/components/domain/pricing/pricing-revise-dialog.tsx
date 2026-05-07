"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

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
import { useReviseProposal } from "@/lib/hooks/pricing/use-pricing-engine";

const FormSchema = z.object({
  newAmount: z
    .string()
    .min(1, "Importe requerido")
    .regex(/^\d+(\.\d{1,2})?$/u, "Hasta 2 decimales"),
  reason: z.string().min(8, "Mínimo 8 caracteres"),
});

type FormValues = z.infer<typeof FormSchema>;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  priceId: string;
  currentAmount: string;
  currency: string;
  onSuccess?: (() => void) | undefined;
}

/**
 * Diálogo de revise: counter-amount + reason obligatorio. Usa
 * `useReviseProposal` (hook S4) y muestra delta vs amount actual.
 */
export function PricingReviseDialog({
  open,
  onOpenChange,
  priceId,
  currentAmount,
  currency,
  onSuccess,
}: Props) {
  const revise = useReviseProposal(priceId);
  const form = useForm<FormValues>({
    resolver: zodResolver(FormSchema),
    defaultValues: { newAmount: "", reason: "" },
    mode: "onChange",
  });

  React.useEffect(() => {
    if (!open) form.reset();
  }, [open, form]);

  const watchedAmount = form.watch("newAmount");
  const delta = React.useMemo(() => {
    const a = Number(watchedAmount);
    const b = Number(currentAmount);
    if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return null;
    const pct = ((a - b) / b) * 100;
    return { abs: a - b, pct };
  }, [watchedAmount, currentAmount]);

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await revise.mutateAsync({
        newAmount: values.newAmount,
        reason: values.reason,
      });
      onOpenChange(false);
      onSuccess?.();
    } catch {
      /* el toast ya lo lanza el hook */
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Revisar propuesta</DialogTitle>
          <DialogDescription>
            Propón un importe alternativo con justificación. Se persiste en el
            historial de aprobación.
          </DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <div className="rounded-md border p-3 text-[12.5px]">
            <div className="flex items-center justify-between">
              <span style={{ color: MT.ink3 }}>Importe actual</span>
              <span className="mt-mono mt-tnum font-semibold">
                {currentAmount} {currency}
              </span>
            </div>
          </div>

          <Field
            label={`Nuevo importe (${currency})`}
            error={form.formState.errors.newAmount?.message}
          >
            <input
              {...form.register("newAmount")}
              type="text"
              inputMode="decimal"
              placeholder="145.99"
              className="w-full rounded-[4px] border px-2 py-1.5 text-[13px] mt-mono mt-tnum"
              style={{ borderColor: MT.border }}
              data-testid="revise-new-amount"
            />
          </Field>

          {delta && Number.isFinite(delta.pct) ? (
            <div className="flex items-center gap-2 text-[12px]">
              <span style={{ color: MT.ink3 }}>Delta:</span>
              <Pill
                tone={
                  Math.abs(delta.pct) > 10
                    ? "warning"
                    : Math.abs(delta.pct) > 25
                      ? "danger"
                      : "neutral"
                }
                mono
              >
                {delta.abs >= 0 ? "+" : ""}
                {delta.abs.toFixed(2)} ({delta.pct.toFixed(1)}%)
              </Pill>
            </div>
          ) : null}

          <Field
            label="Motivo (obligatorio)"
            error={form.formState.errors.reason?.message}
          >
            <textarea
              {...form.register("reason")}
              rows={3}
              placeholder="Cliente solicita ajuste por…"
              className="w-full resize-none rounded-[4px] border px-2 py-1.5 text-[13px]"
              style={{ borderColor: MT.border }}
              data-testid="revise-reason"
            />
          </Field>

          <DialogFooter className="gap-2">
            <MtButton
              tone="ghost"
              type="button"
              onClick={() => onOpenChange(false)}
              disabled={revise.isPending}
            >
              Cancelar
            </MtButton>
            <MtButton
              tone="primary"
              type="submit"
              disabled={revise.isPending || !form.formState.isValid}
              data-testid="revise-submit"
            >
              {revise.isPending ? "Guardando…" : "Revisar"}
            </MtButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span
        className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
        style={{ color: MT.ink3 }}
      >
        {label}
      </span>
      {children}
      {error ? (
        <span className="text-[11.5px]" style={{ color: MT.danger }}>
          {error}
        </span>
      ) : null}
    </label>
  );
}
