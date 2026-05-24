"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import type {
  Channel,
  ChannelState,
  ChannelTransitionResponse,
} from "@/lib/api/endpoints/channels-admin";
import { VALID_TRANSITIONS } from "@/lib/api/endpoints/channels-admin";

// ---------------------------------------------------------------------------
// State display labels
// ---------------------------------------------------------------------------

const STATE_LABEL: Record<ChannelState, string> = {
  inactive: "Inactivo",
  pre_launch: "Pre-lanzamiento",
  pilot: "Piloto",
  live: "Activo",
  paused: "Pausado",
  deprecated: "Deprecado",
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TransitionModalProps {
  channel: Channel | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (params: {
    targetState: ChannelState;
    comment: string;
    overrideWarnings: boolean;
  }) => Promise<void>;
  isPending: boolean;
  lastResult: ChannelTransitionResponse | null;
  lastError: Error | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TransitionModal({
  channel,
  open,
  onOpenChange,
  onConfirm,
  isPending,
  lastResult,
  lastError,
}: TransitionModalProps) {
  const [targetState, setTargetState] = React.useState<ChannelState | "">("");
  const [comment, setComment] = React.useState("");
  const [overrideWarnings, setOverrideWarnings] = React.useState(false);

  // Reset state cuando cambia el canal o se cierra el modal
  React.useEffect(() => {
    if (!open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTargetState("");
      setComment("");
      setOverrideWarnings(false);
    }
  }, [open]);

  // Parse missing_skus from lastError detail si viene de 400
  // Must be before early return to satisfy rules-of-hooks
  const missingSkus: string[] = React.useMemo(() => {
    if (!lastError) return [];
    const msg = lastError.message;
    try {
      // El backend puede envolver el error: {"code":"missing_approved_prices","missing_skus":[...]}
      const parsed: unknown = JSON.parse(msg);
      if (
        parsed !== null &&
        typeof parsed === "object" &&
        "missing_skus" in parsed &&
        Array.isArray((parsed as { missing_skus: unknown }).missing_skus)
      ) {
        return (parsed as { missing_skus: string[] }).missing_skus;
      }
    } catch {
      /* not JSON */
    }
    return [];
  }, [lastError]);

  if (!channel) return null;

  const validTargets = VALID_TRANSITIONS[channel.state] ?? [];
  const showPilotPrereq = targetState === "pilot";
  const showOverrideCheck =
    channel.pilot_with_warnings && targetState !== "";

  const handleConfirm = async () => {
    if (!targetState) return;
    await onConfirm({
      targetState,
      comment,
      overrideWarnings,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Transicionar canal</DialogTitle>
          <DialogDescription>
            Canal{" "}
            <span className="font-mono font-medium">{channel.code}</span>{" "}
            &mdash; estado actual:{" "}
            <span className="font-medium">
              {STATE_LABEL[channel.state]}
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Estado destino */}
          <div className="space-y-1.5">
            <Label htmlFor="target-state">Estado destino</Label>
            {validTargets.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Este canal no tiene transiciones disponibles.
              </p>
            ) : (
              <Select
                value={targetState}
                onValueChange={(v) => setTargetState(v as ChannelState)}
              >
                <SelectTrigger id="target-state">
                  <SelectValue placeholder="Selecciona un estado..." />
                </SelectTrigger>
                <SelectContent>
                  {validTargets.map((s) => (
                    <SelectItem key={s} value={s}>
                      {STATE_LABEL[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Prerrequisito: pilot */}
          {showPilotPrereq && (
            <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
              <strong>Prerrequisito:</strong> Requiere SKUs con precios
              aprobados en este canal antes de activar el piloto.
            </div>
          )}

          {/* Comentario */}
          <div className="space-y-1.5">
            <Label htmlFor="comment">Comentario (opcional)</Label>
            <textarea
              id="comment"
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-none"
              rows={3}
              placeholder="Motivo de la transición..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          {/* Override warnings */}
          {showOverrideCheck && (
            <div className="flex items-center gap-2">
              <input
                id="override-warnings"
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                checked={overrideWarnings}
                onChange={(e) => setOverrideWarnings(e.target.checked)}
              />
              <Label htmlFor="override-warnings" className="font-normal">
                Ignorar advertencias de piloto (
                <code className="font-mono text-xs">override_warnings</code>)
              </Label>
            </div>
          )}

          {/* Errores */}
          {lastError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 space-y-1">
              <p className="font-medium">Error en la transición</p>
              {missingSkus.length > 0 ? (
                <>
                  <p>SKUs sin precios aprobados:</p>
                  <ul className="list-disc pl-4 space-y-0.5">
                    {missingSkus.map((sku) => (
                      <li key={sku} className="font-mono text-xs">
                        {sku}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p>{lastError.message}</p>
              )}
            </div>
          )}

          {/* Resultado con warnings */}
          {lastResult && lastResult.pilot_with_warnings.length > 0 && (
            <div className="rounded-md border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-800 space-y-1">
              <p className="font-medium">
                Transición realizada con advertencias
              </p>
              <p>SKUs en piloto con precios pendientes:</p>
              <div className="flex flex-wrap gap-1 pt-1">
                {lastResult.pilot_with_warnings.map((sku) => (
                  <Badge
                    key={sku}
                    variant="outline"
                    className="font-mono text-xs text-yellow-700 border-yellow-400 bg-yellow-50"
                  >
                    {sku}
                  </Badge>
                ))}
              </div>
              {!overrideWarnings && (
                <p className="pt-1 text-xs">
                  Puedes activar <strong>Ignorar advertencias</strong> y
                  volver a confirmar para proceder de todas formas.
                </p>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancelar
          </Button>
          <Button
            onClick={() => void handleConfirm()}
            disabled={isPending || !targetState || validTargets.length === 0}
          >
            {isPending ? "Procesando..." : "Confirmar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
