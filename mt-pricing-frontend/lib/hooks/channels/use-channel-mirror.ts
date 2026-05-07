"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  channelMirrorApi,
  type DiffResponse,
  type PublishResponse,
  type SyncLogEntry,
} from "@/lib/api/endpoints/channel-mirror";

export const channelMirrorKeys = {
  all: ["channel-mirror"] as const,
  diff: (channel: string, sku: string) =>
    ["channel-mirror", channel, sku, "diff"] as const,
  syncLog: (channel: string) => ["channel-mirror", channel, "sync-log"] as const,
};

export function useChannelDiff(channel: string, sku: string) {
  return useQuery<DiffResponse, Error>({
    queryKey: channelMirrorKeys.diff(channel, sku),
    queryFn: () => channelMirrorApi.diff(channel, sku),
    staleTime: 30_000,
  });
}

export function useChannelSyncLog(channel: string, limit = 5) {
  return useQuery<SyncLogEntry[], Error>({
    queryKey: channelMirrorKeys.syncLog(channel),
    queryFn: () => channelMirrorApi.syncLog(channel, limit),
    staleTime: 60_000,
  });
}

export function useChannelSync(channel: string, sku: string) {
  const qc = useQueryClient();
  return useMutation<DiffResponse, Error, void>({
    mutationFn: () => channelMirrorApi.sync(channel, sku),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: channelMirrorKeys.diff(channel, sku) });
      void qc.invalidateQueries({ queryKey: channelMirrorKeys.syncLog(channel) });
      toast.success("Sync completada");
    },
    onError: (e) => toast.error(`Sync falló: ${e.message}`),
  });
}

export function useChannelPublish(channel: string, sku: string) {
  const qc = useQueryClient();
  return useMutation<PublishResponse, Error, string[] | undefined>({
    mutationFn: (fields) => channelMirrorApi.publish(channel, sku, fields),
    onSuccess: (res) => {
      void qc.invalidateQueries({ queryKey: channelMirrorKeys.diff(channel, sku) });
      void qc.invalidateQueries({ queryKey: channelMirrorKeys.syncLog(channel) });
      toast.success(
        res.accepted_fields.length > 0
          ? `Publicados ${res.accepted_fields.length} campos`
          : "Sin campos publicables",
      );
    },
    onError: (e) => toast.error(`Publish falló: ${e.message}`),
  });
}
