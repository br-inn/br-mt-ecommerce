"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { inventoryApi, type MAPHistoryPoint } from "@/lib/api/endpoints/inventory";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-AE", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}

function fmtAED(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `AED ${parseFloat(value).toLocaleString("en-AE", { minimumFractionDigits: 2 })}`;
}

function DeltaBadge({ before, after }: { before: string | null; after: string }) {
  if (!before) return <Badge variant="secondary">—</Badge>;
  const diff = parseFloat(after) - parseFloat(before);
  if (Math.abs(diff) < 0.0001) {
    return <Badge variant="secondary">Sin cambio</Badge>;
  }
  if (diff < 0) {
    return (
      <Badge className="bg-green-100 text-green-800 border-green-200">
        ▼ {Math.abs(diff).toLocaleString("en-AE", { minimumFractionDigits: 2 })}
      </Badge>
    );
  }
  return (
    <Badge className="bg-red-100 text-red-800 border-red-200">
      ▲ {diff.toLocaleString("en-AE", { minimumFractionDigits: 2 })}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Chart — sparkline SVG nativo (sin recharts)
// ---------------------------------------------------------------------------

function MAPChart({ data }: { data: MAPHistoryPoint[] }) {
  const points = [...data].reverse().map((p) => ({
    date: fmtDate(p.received_at),
    map: parseFloat(p.map_after),
  }));

  if (points.length < 2) return null;

  const W = 600;
  const H = 140;
  const PAD = { top: 8, right: 12, bottom: 28, left: 48 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const values = points.map((p) => p.map);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const rangeV = maxV - minV || 1;

  const toX = (i: number) => PAD.left + (i / (points.length - 1)) * innerW;
  const toY = (v: number) => PAD.top + innerH - ((v - minV) / rangeV) * innerH;

  const polyline = points.map((p, i) => `${toX(i)},${toY(p.map)}`).join(" ");

  // Y-axis: 3 ticks
  const yTicks = [minV, (minV + maxV) / 2, maxV];
  // X-axis: show first, middle, last label
  const xIdxs = [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <div className="mb-4 w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36" aria-hidden>
        {/* Grid lines */}
        {yTicks.map((v) => (
          <line
            key={v}
            x1={PAD.left} x2={PAD.left + innerW}
            y1={toY(v)} y2={toY(v)}
            stroke="#e5e7eb" strokeWidth={1}
          />
        ))}

        {/* Y-axis labels */}
        {yTicks.map((v) => (
          <text
            key={v}
            x={PAD.left - 6} y={toY(v)}
            textAnchor="end" dominantBaseline="middle"
            fontSize={10} fill="#9ca3af"
          >
            {v.toFixed(0)}
          </text>
        ))}

        {/* X-axis labels */}
        {xIdxs.map((i) => (
          <text
            key={i}
            x={toX(i)} y={H - 6}
            textAnchor="middle"
            fontSize={10} fill="#9ca3af"
          >
            {points[i]?.date}
          </text>
        ))}

        {/* Line */}
        <polyline
          points={polyline}
          fill="none"
          stroke="#2563eb"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots with tooltip */}
        {points.map((p, i) => (
          <circle key={i} cx={toX(i)} cy={toY(p.map)} r={3} fill="#2563eb">
            <title>{`${p.date}: AED ${p.map.toLocaleString("en-AE", { minimumFractionDigits: 2 })}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------

interface MAPHistoryDrawerProps {
  sku: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MAPHistoryDrawer({ sku, open, onOpenChange }: MAPHistoryDrawerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["map-history", sku],
    queryFn: () => inventoryApi.getMAPHistory(sku!),
    enabled: !!sku && open,
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-2xl overflow-y-auto">
        <SheetHeader className="mb-4">
          <SheetTitle className="font-mono text-base">
            Historial MAP — {sku ?? ""}
          </SheetTitle>
        </SheetHeader>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No hay recepciones procesadas para este SKU.
          </p>
        ) : (
          <>
            <MAPChart data={data} />

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Fecha</TableHead>
                  <TableHead>PO#</TableHead>
                  <TableHead className="text-right">Qty recibida</TableHead>
                  <TableHead className="text-right">MAP antes</TableHead>
                  <TableHead className="text-right">MAP después</TableHead>
                  <TableHead>Δ MAP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((row) => (
                  <TableRow key={row.gr_id}>
                    <TableCell className="font-mono text-xs">
                      {fmtDate(row.received_at)}
                    </TableCell>
                    <TableCell>
                      <a
                        href={`/compras/pedidos`}
                        className="text-blue-600 hover:underline font-mono text-xs"
                      >
                        {row.po_number}
                      </a>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {parseFloat(row.qty_received).toLocaleString("en-AE", {
                        minimumFractionDigits: 3,
                      })}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {fmtAED(row.map_before)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {fmtAED(row.map_after)}
                    </TableCell>
                    <TableCell>
                      <DeltaBadge before={row.map_before} after={row.map_after} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
