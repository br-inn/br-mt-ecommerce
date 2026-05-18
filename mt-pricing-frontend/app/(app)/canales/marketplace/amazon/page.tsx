"use client";

import * as React from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Download, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  marketplaceListingsApi,
  type AmazonListingValidation,
  type AmazonValidationReport,
} from "@/lib/api/endpoints/marketplace-listings";

import { buildColumns } from "./columns";

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function AmazonListingsPage() {
  const [report, setReport] = React.useState<AmazonValidationReport | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [skuFilter, setSkuFilter] = React.useState("");
  const [generatingSkus, setGeneratingSkus] = React.useState<Set<string>>(new Set());

  // ---- Fetch validation report ----

  const loadReport = React.useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setIsRefreshing(true);
    else setIsLoading(true);
    try {
      const data = await marketplaceListingsApi.validateAmazon();
      setReport(data);
    } catch (err) {
      toast.error("Error al cargar el reporte de validación", {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  React.useEffect(() => {
    void loadReport();
  }, [loadReport]);

  // ---- AI generate ----

  const handleGenerate = React.useCallback(async (sku: string) => {
    setGeneratingSkus((prev) => new Set(prev).add(sku));
    try {
      await marketplaceListingsApi.generateListing(sku);
      toast.success(`Listing generado para ${sku}`, {
        description: "El contenido fue creado por IA exitosamente.",
      });
      // Refresh to reflect the updated state
      void loadReport(false);
    } catch (err) {
      toast.error(`Error al generar listing para ${sku}`, {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setGeneratingSkus((prev) => {
        const next = new Set(prev);
        next.delete(sku);
        return next;
      });
    }
  }, [loadReport]);

  // ---- Table setup ----

  const columns = React.useMemo(
    () => buildColumns({ onGenerate: handleGenerate, generatingSkus }),
    [handleGenerate, generatingSkus],
  );

  const data: AmazonListingValidation[] = report?.listings ?? [];

  const table = useReactTable({
    data,
    columns,
    state: {
      globalFilter: skuFilter,
    },
    onGlobalFilterChange: setSkuFilter,
    globalFilterFn: (row, _columnId, filterValue: string) =>
      row.original.sku.toLowerCase().includes((filterValue as string).toLowerCase()),
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  // ---- Export ----

  const handleExport = () => {
    window.open(marketplaceListingsApi.getExportUrl(), "_blank");
  };

  // ---- Render ----

  return (
    <div className="space-y-6">
      {/* Header */}
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Amazon UAE Listings</h1>
          <p className="text-sm text-muted-foreground">
            {report ? (
              <>
                <span className="font-medium text-foreground">{report.total_skus}</span> SKUs totales
                {" · "}
                <Badge className="border-transparent bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 text-xs">
                  {report.ready_count} listos
                </Badge>
                {" "}
                <Badge variant="destructive" className="text-xs">
                  {report.error_count} con errores
                </Badge>
                {report.draft_count > 0 && (
                  <>
                    {" "}
                    <Badge variant="secondary" className="text-xs">
                      {report.draft_count} borradores
                    </Badge>
                  </>
                )}
              </>
            ) : (
              "Validación y exportación de listings para Amazon UAE"
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadReport(true)}
            disabled={isLoading || isRefreshing}
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            {isRefreshing ? "Actualizando…" : "Actualizar"}
          </Button>
          <Button
            size="sm"
            onClick={handleExport}
            disabled={isLoading || !report}
          >
            <Download className="h-4 w-4" />
            Exportar CSV
          </Button>
        </div>
      </header>

      {/* Filter */}
      <Input
        placeholder="Filtrar por SKU…"
        value={skuFilter}
        onChange={(e) => setSkuFilter(e.target.value)}
        className="max-w-xs"
      />

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-md" />
          ))}
        </div>
      ) : (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={columns.length}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No se encontraron productos.
                  </TableCell>
                </TableRow>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
