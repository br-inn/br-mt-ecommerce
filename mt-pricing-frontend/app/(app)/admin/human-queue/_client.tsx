"use client";

import * as React from "react";
import { toast } from "sonner";
import { CheckCircle, MinusCircle, SkipForward } from "lucide-react";

import { MatchCard } from "@/components/domain/matching/MatchCard";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useHumanQueue, useLabelMatch } from "@/lib/hooks/human-queue/use-human-queue";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { HumanQueueApiError } from "@/lib/api/endpoints/human-queue";
import type { HumanQueueItem, HumanQueueLabel } from "@/lib/api/endpoints/human-queue";

// ---------------------------------------------------------------------------
// Confidence badge
// ---------------------------------------------------------------------------
function ConfidenceBadge({ value }: { value: string | null }) {
  if (value === null || value === undefined) {
    return <Badge variant="outline">N/A</Badge>;
  }
  const num = parseFloat(value);
  if (num < 0.5) {
    return (
      <Badge className="bg-red-500 text-white border-transparent hover:bg-red-500/90">
        {(num * 100).toFixed(0)}%
      </Badge>
    );
  }
  if (num < 0.75) {
    return (
      <Badge className="bg-yellow-400 text-yellow-900 border-transparent hover:bg-yellow-400/90">
        {(num * 100).toFixed(0)}%
      </Badge>
    );
  }
  return (
    <Badge className="bg-green-600 text-white border-transparent hover:bg-green-600/90">
      {(num * 100).toFixed(0)}%
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Action buttons
// ---------------------------------------------------------------------------
interface ActionButtonsProps {
  item: HumanQueueItem;
  onLabel: (id: string, label: HumanQueueLabel) => void;
  isLoading: boolean;
  canWrite: boolean;
}

function ActionButtons({ item, onLabel, isLoading, canWrite }: ActionButtonsProps) {
  if (!canWrite) {
    return <span className="text-xs text-muted-foreground">Sin permiso</span>;
  }
  if (item.label) {
    return (
      <span className="text-xs text-muted-foreground capitalize">
        {item.label === "accept" && "Aceptado"}
        {item.label === "reject" && "Rechazado"}
        {item.label === "skip" && "Omitido"}
      </span>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <Button
        size="sm"
        variant="default"
        className="h-7 bg-green-600 hover:bg-green-700"
        disabled={isLoading}
        onClick={() => onLabel(item.id, "accept")}
        title="Aceptar match"
      >
        <CheckCircle className="size-3.5 mr-1" />
        Aceptar
      </Button>
      <Button
        size="sm"
        variant="destructive"
        className="h-7"
        disabled={isLoading}
        onClick={() => onLabel(item.id, "reject")}
        title="Rechazar match"
      >
        <MinusCircle className="size-3.5 mr-1" />
        Rechazar
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-7"
        disabled={isLoading}
        onClick={() => onLabel(item.id, "skip")}
        title="Omitir por ahora"
      >
        <SkipForward className="size-3.5 mr-1" />
        Omitir
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------
const PAGE_SIZE = 50;

export function HumanQueueClient() {
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("matches:write");

  const [offset, setOffset] = React.useState(0);
  const [labellingId, setLabellingId] = React.useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useHumanQueue({
    limit: PAGE_SIZE,
    offset,
  });

  const labelMutation = useLabelMatch();

  const handleLabel = async (id: string, label: HumanQueueLabel) => {
    setLabellingId(id);
    try {
      await labelMutation.mutateAsync({ matchId: id, payload: { label } });
      const labelText =
        label === "accept" ? "Aceptado" : label === "reject" ? "Rechazado" : "Omitido";
      toast.success(`Match ${labelText.toLowerCase()} correctamente.`);
    } catch (err) {
      const msg =
        err instanceof HumanQueueApiError
          ? err.message
          : "Error al aplicar etiqueta.";
      toast.error(msg);
    } finally {
      setLabellingId(null);
    }
  };

  // Feature flag: backend devuelve 503 cuando está deshabilitado
  if (isError && error instanceof HumanQueueApiError && error.status === 503) {
    return (
      <div className="rounded-md border border-muted bg-muted/30 p-6 text-center text-sm text-muted-foreground">
        Cola de validación humana deshabilitada (
        <code className="font-mono text-xs">HUMAN_QUEUE_ENABLED=false</code>).
      </div>
    );
  }

  if (isError) {
    return (
      <MtError
        message={
          error instanceof Error ? error.message : "Error al cargar la cola. Inténtalo de nuevo."
        }
        onRetry={() => void refetch()}
      />
    );
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasMore = items.length === PAGE_SIZE;
  const hasPrev = offset > 0;

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      {data && (
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span>
            Mostrando {items.length} ítem{items.length !== 1 ? "s" : ""}
          </span>
          <span>·</span>
          <span>
            Umbral: confianza &lt;{" "}
            <strong>{(data.confidence_threshold * 100).toFixed(0)}%</strong>
          </span>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <MtSkeleton key={i} width="100%" height={56} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <MtEmpty
          title="Cola vacía"
          hint="No hay matches pendientes de revisión con confianza baja. ¡Todo al día!"
        />
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-[280px]">Par candidato / producto MT</TableHead>
                <TableHead className="w-[100px]">Confianza</TableHead>
                <TableHead className="w-[80px]">Canal</TableHead>
                <TableHead className="w-[120px]">SKU MT</TableHead>
                <TableHead className="w-[300px]">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow
                  key={item.id}
                  className={
                    item.label
                      ? "opacity-60 bg-muted/20"
                      : undefined
                  }
                >
                  <TableCell>
                    <MatchCard
                      item={item}
                      candidateImageUrl={
                        typeof item.specs_jsonb?.image_url === "string"
                          ? item.specs_jsonb.image_url
                          : null
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <ConfidenceBadge value={item.calibrated_confidence} />
                  </TableCell>
                  <TableCell>
                    <span className="text-xs">
                      {item.channel.replace("_", " ")}
                    </span>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs font-mono">{item.product_sku}</code>
                  </TableCell>
                  <TableCell>
                    <ActionButtons
                      item={item}
                      onLabel={handleLabel}
                      isLoading={labellingId === item.id}
                      canWrite={canWrite}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Paginación */}
      {(hasPrev || hasMore) && (
        <div className="flex items-center justify-between pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev || isLoading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Anterior
          </Button>
          <span className="text-xs text-muted-foreground">
            Página {Math.floor(offset / PAGE_SIZE) + 1}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasMore || isLoading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Siguiente
          </Button>
        </div>
      )}
    </div>
  );
}
