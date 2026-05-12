"use client";

import * as React from "react";
import { toast } from "sonner";
import { Clock } from "lucide-react";

import { MtError } from "@/components/mt/states";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { usePermissions } from "@/lib/hooks/use-permissions";
import {
  useChannels,
  useChannelHistory,
  useTransitionChannel,
} from "@/lib/hooks/channels/use-channels-admin";
import { ChannelsAdminApiError } from "@/lib/api/endpoints/channels-admin";
import type {
  Channel,
  ChannelState,
  ChannelTransitionResponse,
} from "@/lib/api/endpoints/channels-admin";

import { ChannelTable } from "./components/channel-table";
import { TransitionModal } from "./components/transition-modal";

// ---------------------------------------------------------------------------
// State label helper (shared)
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
// Timeline de historial
// ---------------------------------------------------------------------------

function ChannelHistoryTimeline({ channelId }: { channelId: string }) {
  const { data: history, isLoading } = useChannelHistory(channelId);

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground animate-pulse">
        Cargando historial...
      </p>
    );
  }

  if (!history || history.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin historial de transiciones.
      </p>
    );
  }

  return (
    <ol className="relative border-l border-border space-y-4 pl-4">
      {history.map((entry) => (
        <li key={entry.id} className="relative">
          <div className="absolute -left-[19px] top-1 size-3 rounded-full bg-primary/70 border-2 border-background" />
          <div className="text-xs text-muted-foreground">
            {new Date(entry.created_at).toLocaleString("es-AE", {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </div>
          <div className="text-sm mt-0.5">
            <span className="font-medium">
              {entry.from_state ? STATE_LABEL[entry.from_state] : "—"}
            </span>{" "}
            &rarr;{" "}
            <span className="font-medium">{STATE_LABEL[entry.to_state]}</span>
          </div>
          {entry.comment && (
            <div className="text-xs text-muted-foreground mt-0.5 italic">
              &ldquo;{entry.comment}&rdquo;
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

export function ChannelsClient() {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("channels:manage");

  const { data: channels, isLoading, isError, error, refetch } = useChannels();

  const [selectedChannelId, setSelectedChannelId] = React.useState<
    string | null
  >(null);
  const [modalChannel, setModalChannel] = React.useState<Channel | null>(null);
  const [lastResult, setLastResult] =
    React.useState<ChannelTransitionResponse | null>(null);
  const [lastError, setLastError] = React.useState<Error | null>(null);

  const transitionMutation = useTransitionChannel();

  const handleOpenTransition = (channel: Channel) => {
    setModalChannel(channel);
    setLastResult(null);
    setLastError(null);
  };

  const handleConfirmTransition = async ({
    targetState,
    comment,
    overrideWarnings,
  }: {
    targetState: ChannelState;
    comment: string;
    overrideWarnings: boolean;
  }) => {
    if (!modalChannel) return;

    setLastError(null);
    setLastResult(null);

    try {
      const trimmedComment = comment.trim();
      const result = await transitionMutation.mutateAsync({
        channelId: modalChannel.id,
        payload: {
          target_state: targetState,
          ...(trimmedComment ? { comment: trimmedComment } : {}),
          override_warnings: overrideWarnings,
        },
      });

      setLastResult(result);

      if (result.pilot_with_warnings.length > 0) {
        toast.warning(
          `Canal ${result.channel_code} en piloto con ${result.pilot_with_warnings.length} SKU(s) con advertencias.`,
        );
      } else {
        toast.success(
          `Canal ${result.channel_code} transicionado a ${STATE_LABEL[result.to_state]}.`,
        );
        setModalChannel(null);
      }
    } catch (err) {
      const apiErr =
        err instanceof ChannelsAdminApiError ? err : (err as Error);
      setLastError(apiErr);
      toast.error(
        `Error al transicionar: ${apiErr.message ?? "Error desconocido"}`,
      );
    }
  };

  if (isError) {
    return (
      <MtError
        message={
          error instanceof Error
            ? error.message
            : "Error al cargar canales. Inténtalo de nuevo."
        }
        onRetry={() => void refetch()}
      />
    );
  }

  const channelList = channels ?? [];
  const selectedChannel =
    channelList.find((c) => c.id === selectedChannelId) ?? null;

  return (
    <div className="space-y-6">
      {/* Tabla principal */}
      <Card>
        <CardHeader>
          <CardTitle>Canales de venta</CardTitle>
          <CardDescription>
            Gestión del ciclo de vida de los canales MT. Haz clic en una fila
            para ver su historial de transiciones.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ChannelTable
            channels={channelList}
            isLoading={isLoading}
            canManage={canManage}
            selectedChannelId={selectedChannelId}
            onSelectChannel={(id) =>
              setSelectedChannelId((prev) => (prev === id ? null : id))
            }
            onTransition={handleOpenTransition}
          />
        </CardContent>
      </Card>

      {/* Panel de historial (visible cuando hay canal seleccionado) */}
      {selectedChannel && (
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 space-y-0 pb-3">
            <Clock className="size-4 text-muted-foreground" />
            <CardTitle className="text-base">
              Historial — {selectedChannel.code}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChannelHistoryTimeline channelId={selectedChannel.id} />
          </CardContent>
        </Card>
      )}

      {/* Modal de transición */}
      <TransitionModal
        channel={modalChannel}
        open={!!modalChannel}
        onOpenChange={(open) => {
          if (!open) setModalChannel(null);
        }}
        onConfirm={handleConfirmTransition}
        isPending={transitionMutation.isPending}
        lastResult={lastResult}
        lastError={lastError}
      />
    </div>
  );
}
