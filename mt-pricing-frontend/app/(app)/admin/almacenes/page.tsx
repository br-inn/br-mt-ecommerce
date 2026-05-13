/**
 * `/admin/almacenes` — Jerarquía de almacenes: Warehouse → Zone → Location.
 *
 * US-ERP-02-04: lista de almacenes con sus zonas expandibles.
 * RBAC: purchases:write (mismo permiso que el resto del módulo de inventario).
 */
"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Warehouse } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  inventoryApi,
  type WarehouseRead,
  type WarehouseZoneRead,
} from "@/lib/api/endpoints/inventory";

// ---------------------------------------------------------------------------
// Zone row (expanded)
// ---------------------------------------------------------------------------

function ZoneRows({ warehouseId }: { warehouseId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["warehouse-zones", warehouseId],
    queryFn: () => inventoryApi.listZones(warehouseId),
    staleTime: 60_000,
  });

  const ZONE_TYPE_LABEL: Record<string, string> = {
    refrigerated: "Refrigerada",
    dry: "Seco",
    hazardous: "Peligroso",
    general: "General",
  };

  if (isLoading) {
    return (
      <TableRow>
        <TableCell colSpan={4} className="pl-12 py-2">
          <Skeleton className="h-4 w-64" />
        </TableCell>
      </TableRow>
    );
  }

  if (!data || data.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={4} className="pl-12 py-2 text-xs text-muted-foreground">
          Sin zonas registradas.
        </TableCell>
      </TableRow>
    );
  }

  return (
    <>
      {data.map((zone: WarehouseZoneRead) => (
        <TableRow key={zone.id} className="bg-muted/30">
          <TableCell className="pl-12 text-xs font-mono">{zone.code}</TableCell>
          <TableCell className="text-sm">{zone.name}</TableCell>
          <TableCell>
            {zone.zone_type ? (
              <Badge variant="secondary" className="text-xs">
                {ZONE_TYPE_LABEL[zone.zone_type] ?? zone.zone_type}
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">—</span>
            )}
          </TableCell>
          <TableCell />
        </TableRow>
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Warehouse row (collapsible)
// ---------------------------------------------------------------------------

function WarehouseRow({ wh }: { wh: WarehouseRead }) {
  const [expanded, setExpanded] = React.useState(false);

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/50"
        onClick={() => setExpanded((v) => !v)}
      >
        <TableCell className="w-8">
          {expanded ? (
            <ChevronDown className="size-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-4 text-muted-foreground" />
          )}
        </TableCell>
        <TableCell className="font-mono text-xs font-medium">{wh.code}</TableCell>
        <TableCell className="text-sm font-medium">{wh.name}</TableCell>
        <TableCell className="text-xs text-muted-foreground">{wh.address ?? "—"}</TableCell>
        <TableCell>
          <Badge
            variant={wh.is_active ? "default" : "secondary"}
            className="text-xs"
          >
            {wh.is_active ? "Activo" : "Inactivo"}
          </Badge>
        </TableCell>
      </TableRow>
      {expanded && <ZoneRows warehouseId={wh.id} />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AlmacenesPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["warehouses"],
    queryFn: () => inventoryApi.listWarehouses(),
    staleTime: 60_000,
  });

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-center gap-3">
        <Warehouse className="size-6 text-muted-foreground" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Almacenes</h1>
          <p className="text-sm text-muted-foreground">
            Jerarquía Warehouse → Zona → Ubicación (bin)
          </p>
        </div>
      </header>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Lista de almacenes</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isError ? (
            <p className="px-6 py-4 text-sm text-destructive">
              Error al cargar almacenes.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Código</TableHead>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Dirección</TableHead>
                  <TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <TableRow key={i}>
                        {Array.from({ length: 5 }).map((__, j) => (
                          <TableCell key={j}>
                            <Skeleton className="h-4 w-full" />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  : (data ?? []).map((wh) => (
                      <WarehouseRow key={wh.id} wh={wh} />
                    ))}
                {!isLoading && (data ?? []).length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      className="py-10 text-center text-sm text-muted-foreground"
                    >
                      No hay almacenes registrados.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
