"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateExceptionRule } from "@/lib/hooks/exception-rules/use-exception-rules";

interface RuleFormProps {
  onSuccess?: () => void;
}

/**
 * Formulario modal para crear una nueva exception rule.
 * La regla se crea inactiva; hay que activarla explícitamente desde la tabla.
 */
export function RuleForm({ onSuccess }: RuleFormProps) {
  const [open, setOpen] = React.useState(false);
  const createMutation = useCreateExceptionRule();

  const [code, setCode] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [marginPct, setMarginPct] = React.useState("");
  const [fxPct, setFxPct] = React.useState("");
  const [minMarginPct, setMinMarginPct] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  function reset() {
    setCode("");
    setDescription("");
    setMarginPct("");
    setFxPct("");
    setMinMarginPct("");
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!code.trim()) {
      setError("El código es obligatorio.");
      return;
    }
    try {
      await createMutation.mutateAsync({
        code: code.trim(),
        description: description.trim() || null,
        margin_threshold_pct: marginPct || null,
        fx_swing_threshold_pct: fxPct || null,
        min_margin_pct: minMarginPct || null,
      });
      reset();
      setOpen(false);
      onSuccess?.();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Error al crear la regla.";
      setError(msg);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">Nueva regla</Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nueva exception rule</DialogTitle>
          <DialogDescription>
            La regla se crea inactiva. Actívala desde la tabla para que entre en
            vigencia.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          <div className="space-y-1">
            <Label htmlFor="er-code">Código *</Label>
            <Input
              id="er-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="ej. margin_b2c_default"
              maxLength={64}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="er-desc">Descripción</Label>
            <Input
              id="er-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Descripción opcional"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label htmlFor="er-margin" className="text-xs">
                Umbral margen %
              </Label>
              <Input
                id="er-margin"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={marginPct}
                onChange={(e) => setMarginPct(e.target.value)}
                placeholder="5.00"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="er-fx" className="text-xs">
                Umbral FX %
              </Label>
              <Input
                id="er-fx"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={fxPct}
                onChange={(e) => setFxPct(e.target.value)}
                placeholder="3.00"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="er-minmargin" className="text-xs">
                Margen mín. %
              </Label>
              <Input
                id="er-minmargin"
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={minMarginPct}
                onChange={(e) => setMinMarginPct(e.target.value)}
                placeholder="8.00"
              />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear regla"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
