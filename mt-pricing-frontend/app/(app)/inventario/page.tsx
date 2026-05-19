/**
 * `/inventario` — Dashboard de posiciones de inventario y KPIs.
 *
 * Tab "Posiciones": tabla filtrable con drawer de historial MAP.
 * Tab "Resumen": 4 cards de KPIs agregados.
 */
"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { MAPHistoryDrawer } from "@/components/inventario/map-history-drawer";
import {
  inventoryApi,
  type InventoryPositionRead,
  type StockMovementRead,
} from "@/lib/api/endpoints/inventory";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SCHEME_OPTIONS = [
  { value: "__all__", label: "Todos los schemes" },
  { value: "FBA", label: "FBA" },
  { value: "FBM", label: "FBM" },
  { value: "DIRECT_B2C", label: "Direct B2C" },
  { value: "DIRECT_B2B", label: "Direct B2B" },
  { value: "MARKETPLACE", label: "Marketplace" },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtAED(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return parseFloat(value).toLocaleString("en-AE", { minimumFractionDigits: 2 });
}

function fmtQty(value: string): string {
  return parseFloat(value).toLocaleString("en-AE", { minimumFractionDigits: 3 });
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-AE", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Tab Posiciones
// ---------------------------------------------------------------------------

function PositionsTab() {
  const [schemeFilter, setSchemeFilter] = React.useState<string>("__all__");
  const [selectedSku, setSelectedSku] = React.useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["inventory-positions", schemeFilter],
    queryFn: () =>
      inventoryApi.listPositions({
        scheme_code: schemeFilter === "__all__" ? undefined : schemeFilter,
      }),
    staleTime: 30_000,
  });

  function handleRowClick(sku: string) {
    setSelectedSku(sku);
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={schemeFilter} onValueChange={setSchemeFilter}>
          <SelectTrigger className="w-52">
            <SelectValue placeholder="Todos los schemes" />
          </SelectTrigger>
          <SelectContent>
            {SCHEME_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tabla */}
      {isError ? (
        <p className="text-sm text-destructive">Error al cargar posiciones.</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Descripción</TableHead>
                <TableHead>Proveedor</TableHead>
                <TableHead>Scheme</TableHead>
                <TableHead className="text-right">Qty stock</TableHead>
                <TableHead className="text-right">MAP (AED)</TableHead>
                <TableHead className="text-right">Valor stock (AED)</TableHead>
                <TableHead>Última recepción</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : (data ?? []).map((pos) => (
                    <PositionRow
                      key={pos.id}
                      pos={pos}
                      onClick={() => handleRowClick(pos.sku)}
                    />
                  ))}
              {!isLoading && (data ?? []).length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="py-8 text-center text-sm text-muted-foreground"
                  >
                    No hay posiciones de inventario.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <MAPHistoryDrawer
        sku={selectedSku}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </div>
  );
}

function PositionRow({
  pos,
  onClick,
}: {
  pos: InventoryPositionRead;
  onClick: () => void;
}) {
  const noStock = parseFloat(pos.qty_on_hand) === 0;

  return (
    <TableRow
      className={`cursor-pointer hover:bg-muted/50 ${noStock ? "bg-gray-50" : ""}`}
      onClick={onClick}
    >
      <TableCell className="font-mono text-xs font-medium">{pos.sku}</TableCell>
      <TableCell className="max-w-48 truncate text-sm">
        {pos.product_name ?? "—"}
      </TableCell>
      <TableCell className="text-sm">{pos.supplier_code}</TableCell>
      <TableCell>
        <Badge variant="outline" className="font-mono text-xs">
          {pos.scheme_code}
        </Badge>
      </TableCell>
      <TableCell className="text-right font-mono text-xs">
        {fmtQty(pos.qty_on_hand)}
      </TableCell>
      <TableCell className="text-right font-mono text-xs">
        {pos.map_aed === null ? (
          <Badge variant="destructive" className="text-xs">
            Sin coste
          </Badge>
        ) : (
          fmtAED(pos.map_aed)
        )}
      </TableCell>
      <TableCell className="text-right font-mono text-xs">
        {fmtAED(pos.total_stock_value_aed)}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {fmtDate(pos.last_updated_at)}
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Tab Movimientos
// ---------------------------------------------------------------------------

function MovimientosTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["inventory-movements"],
    queryFn: () => inventoryApi.listMovements(100),
    staleTime: 30_000,
  });

  const DIRECTION_LABEL: Record<string, string> = {
    IN: "Entrada",
    OUT: "Salida",
    TRANSFER: "Traslado",
  };

  const DIRECTION_COLOR: Record<string, string> = {
    IN: "text-emerald-700",
    OUT: "text-red-600",
    TRANSFER: "text-blue-600",
  };

  return (
    <div className="space-y-4">
      {isError ? (
        <p className="text-sm text-destructive">Error al cargar movimientos.</p>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Dirección</TableHead>
                <TableHead>Producto</TableHead>
                <TableHead className="text-right">Cantidad</TableHead>
                <TableHead>Referencia</TableHead>
                <TableHead>Notas</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading
                ? Array.from({ length: 6 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 7 }).map((__, j) => (
                        <TableCell key={j}>
                          <Skeleton className="h-4 w-full" />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))
                : (data ?? []).map((mv) => (
                    <MovementRow
                      key={mv.id}
                      mv={mv}
                      directionLabel={DIRECTION_LABEL}
                      directionColor={DIRECTION_COLOR}
                    />
                  ))}
              {!isLoading && (data ?? []).length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-8 text-center text-sm text-muted-foreground"
                  >
                    No hay movimientos registrados.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function MovementRow({
  mv,
  directionLabel,
  directionColor,
}: {
  mv: StockMovementRead;
  directionLabel: Record<string, string>;
  directionColor: Record<string, string>;
}) {
  return (
    <TableRow>
      <TableCell className="text-xs text-muted-foreground">
        {fmtDate(mv.posted_at)}
      </TableCell>
      <TableCell className="font-mono text-xs">{mv.movement_type_id}</TableCell>
      <TableCell>
        <span className={`text-xs font-medium ${directionColor["IN"] ?? ""}`}>
          {directionLabel["IN"] ?? mv.movement_type_id}
        </span>
      </TableCell>
      <TableCell className="font-mono text-xs">{mv.product_sku}</TableCell>
      <TableCell className="text-right font-mono text-xs">
        {parseFloat(mv.qty).toLocaleString("en-AE", { minimumFractionDigits: 4 })}
      </TableCell>
      <TableCell className="text-xs">
        {mv.reference_type ? (
          <Badge variant="outline" className="font-mono text-xs">
            {mv.reference_type}
          </Badge>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell className="max-w-40 truncate text-xs text-muted-foreground">
        {mv.notes ?? "—"}
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Tab Resumen
// ---------------------------------------------------------------------------

function SummaryTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["inventory-summary"],
    queryFn: () => inventoryApi.getSummary(),
    staleTime: 60_000,
  });

  const cards: Array<{
    title: string;
    value: React.ReactNode;
    alert?: boolean;
    alertColor?: "red" | "yellow";
  }> = [
    {
      title: "SKUs con stock",
      value: isLoading ? (
        <Skeleton className="h-8 w-16" />
      ) : (
        <span className="text-3xl font-bold tabular-nums">
          {data?.total_skus_with_stock ?? 0}
        </span>
      ),
    },
    {
      title: "Valor inventario AED",
      value: isLoading ? (
        <Skeleton className="h-8 w-40" />
      ) : (
        <span className="text-xl font-bold tabular-nums">
          AED{" "}
          {data
            ? parseFloat(data.total_stock_value_aed).toLocaleString("en-AE", {
                minimumFractionDigits: 2,
              })
            : "0.00"}
        </span>
      ),
    },
    {
      title: "SKUs sin coste",
      value: isLoading ? (
        <Skeleton className="h-8 w-12" />
      ) : (
        <span
          className={`text-3xl font-bold tabular-nums ${
            (data?.skus_without_cost ?? 0) > 0 ? "text-red-600" : ""
          }`}
        >
          {data?.skus_without_cost ?? 0}
        </span>
      ),
      alert: (data?.skus_without_cost ?? 0) > 0,
      alertColor: "red",
    },
    {
      title: "GRs pendientes >5min",
      value: isLoading ? (
        <Skeleton className="h-8 w-12" />
      ) : (
        <span
          className={`text-3xl font-bold tabular-nums ${
            (data?.pending_gr_count ?? 0) > 0 ? "text-amber-600" : ""
          }`}
        >
          {data?.pending_gr_count ?? 0}
        </span>
      ),
      alert: (data?.pending_gr_count ?? 0) > 0,
      alertColor: "yellow",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card
          key={card.title}
          className={
            card.alert
              ? card.alertColor === "red"
                ? "border-red-200"
                : "border-amber-200"
              : ""
          }
        >
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {card.title}
            </CardTitle>
          </CardHeader>
          <CardContent>{card.value}</CardContent>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InventarioPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Inventario</h1>
        <p className="text-sm text-muted-foreground">
          Posiciones de stock por SKU · Scheme · Proveedor
        </p>
      </header>

      <Tabs defaultValue="posiciones">
        <TabsList>
          <TabsTrigger value="posiciones">Posiciones</TabsTrigger>
          <TabsTrigger value="movimientos">Movimientos</TabsTrigger>
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
        </TabsList>

        <TabsContent value="posiciones" className="mt-4">
          <PositionsTab />
        </TabsContent>

        <TabsContent value="movimientos" className="mt-4">
          <MovimientosTab />
        </TabsContent>

        <TabsContent value="resumen" className="mt-4">
          <SummaryTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
