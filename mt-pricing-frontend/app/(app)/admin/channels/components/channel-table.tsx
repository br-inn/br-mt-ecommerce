"use client";

import * as React from "react";

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
import { MtEmpty, MtSkeleton } from "@/components/mt/states";
import type { Channel, ChannelState } from "@/lib/api/endpoints/channels-admin";

// ---------------------------------------------------------------------------
// State badge
// ---------------------------------------------------------------------------

const STATE_LABEL: Record<ChannelState, string> = {
  inactive: "Inactivo",
  pre_launch: "Pre-lanzamiento",
  pilot: "Piloto",
  live: "Activo",
  paused: "Pausado",
  deprecated: "Deprecado",
};

const STATE_VARIANT: Record<
  ChannelState,
  "secondary" | "outline" | "destructive" | "default"
> = {
  inactive: "secondary",
  pre_launch: "outline",
  pilot: "outline",
  live: "default",
  paused: "outline",
  deprecated: "destructive",
};

/** Inline color class override por estado */
const STATE_COLOR_CLASS: Record<ChannelState, string> = {
  inactive: "text-gray-500 border-gray-300 bg-gray-50",
  pre_launch: "text-blue-600 border-blue-300 bg-blue-50",
  pilot: "text-yellow-700 border-yellow-400 bg-yellow-50",
  live: "text-green-700 border-green-400 bg-green-50",
  paused: "text-orange-700 border-orange-400 bg-orange-50",
  deprecated: "text-red-700 border-red-400 bg-red-50",
};

function StateBadge({ state }: { state: ChannelState }) {
  return (
    <Badge
      variant={STATE_VARIANT[state]}
      className={STATE_COLOR_CLASS[state]}
    >
      {STATE_LABEL[state]}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChannelTableProps {
  channels: Channel[];
  isLoading: boolean;
  canManage: boolean;
  selectedChannelId: string | null;
  onSelectChannel: (id: string) => void;
  onTransition: (channel: Channel) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChannelTable({
  channels,
  isLoading,
  canManage,
  selectedChannelId,
  onSelectChannel,
  onTransition,
}: ChannelTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <MtSkeleton key={i} height={48} className="w-full" />
        ))}
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <MtEmpty
        title="Sin canales"
        hint="No hay canales registrados en el sistema."
      />
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[140px]">Código</TableHead>
            <TableHead>Nombre</TableHead>
            <TableHead className="w-[160px]">Estado</TableHead>
            <TableHead className="w-[140px]">Pilot warnings</TableHead>
            <TableHead className="w-[120px] text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {channels.map((ch) => (
            <TableRow
              key={ch.id}
              className={
                selectedChannelId === ch.id
                  ? "bg-muted/40 cursor-pointer"
                  : "cursor-pointer hover:bg-muted/20"
              }
              onClick={() => onSelectChannel(ch.id)}
            >
              <TableCell className="font-mono text-xs">{ch.code}</TableCell>
              <TableCell>{ch.name}</TableCell>
              <TableCell>
                <StateBadge state={ch.state} />
              </TableCell>
              <TableCell>
                {ch.pilot_with_warnings ? (
                  <Badge
                    variant="outline"
                    className="text-yellow-700 border-yellow-400 bg-yellow-50"
                  >
                    Con advertencias
                  </Badge>
                ) : (
                  <span className="text-muted-foreground text-sm">—</span>
                )}
              </TableCell>
              <TableCell className="text-right">
                {canManage ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      onTransition(ch);
                    }}
                  >
                    Transicionar
                  </Button>
                ) : (
                  <span className="text-muted-foreground text-xs">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
