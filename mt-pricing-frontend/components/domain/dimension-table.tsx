"use client";

import { useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  useActuationCodes,
  useProductDimensions,
} from "@/lib/hooks/use-dimensions";
import type {
  ActuationCode,
  DimensionCell,
  DimensionColumn,
  DimensionRowWithCells,
} from "@/lib/api/types-dimensions";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DimensionTableProps {
  sku: string;
}

// ---------------------------------------------------------------------------
// Helpers (exported for unit tests)
// ---------------------------------------------------------------------------

/**
 * Format a column header label combining `label_en` with the unit suffix
 * (e.g. "A (mm)"). Returns just `label_en` when no unit is present.
 */
export function formatColumnHeader(col: DimensionColumn): string {
  if (col.unit && col.unit.trim() !== "") {
    return `${col.label_en} (${col.unit})`;
  }
  return col.label_en;
}

/**
 * Convert a wire-format cell value to its display string.
 * - `value_number` (Decimal): formatted with 3 decimals when unit is `kg`,
 *   else 2 decimals.
 * - `value_text`: returned verbatim.
 * - Neither: returns the em-dash placeholder.
 */
export function renderCellValue(
  cell: DimensionCell | undefined,
  column: DimensionColumn | undefined,
): string {
  if (!cell) return "—";
  if (cell.value_number !== null && cell.value_number !== undefined) {
    const n = Number(cell.value_number);
    if (Number.isNaN(n)) return "—";
    const decimals = column?.unit === "kg" ? 3 : 2;
    return n.toFixed(decimals);
  }
  if (cell.value_text !== null && cell.value_text !== undefined) {
    return cell.value_text;
  }
  return "—";
}

/**
 * Resolve `actuation_code_id` against the catalogue to its human-readable
 * code (e.g. "M1", "G2"). Falls back to em-dash when the id is null or
 * unknown.
 */
export function resolveActuationLabel(
  actuationCodeId: string | null,
  catalogue: ActuationCode[] | undefined,
): string {
  if (!actuationCodeId) return "—";
  const hit = catalogue?.find((c) => c.id === actuationCodeId);
  return hit?.code ?? "—";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DimensionTable({ sku }: DimensionTableProps) {
  const dimsQuery = useProductDimensions(sku);
  const actsQuery = useActuationCodes();

  const sortedColumns = useMemo<DimensionColumn[]>(() => {
    if (!dimsQuery.data) return [];
    return [...dimsQuery.data.columns].sort(
      (a, b) => a.order_index - b.order_index,
    );
  }, [dimsQuery.data]);

  const sortedRows = useMemo<DimensionRowWithCells[]>(() => {
    if (!dimsQuery.data) return [];
    return [...dimsQuery.data.rows].sort(
      (a, b) => a.order_index - b.order_index,
    );
  }, [dimsQuery.data]);

  // Index cells per row for O(1) lookup keyed by column_id.
  const cellsByRowAndColumn = useMemo(() => {
    const map = new Map<string, Map<string, DimensionCell>>();
    for (const row of sortedRows) {
      const colMap = new Map<string, DimensionCell>();
      for (const cell of row.cells) {
        colMap.set(cell.column_id, cell);
      }
      map.set(row.id, colMap);
    }
    return map;
  }, [sortedRows]);

  // Hide the Actuation column entirely if no row uses it.
  const showActuationColumn = useMemo(
    () => sortedRows.some((r) => r.actuation_code_id !== null),
    [sortedRows],
  );

  if (!dimsQuery.isLoading && (sortedColumns.length === 0 || sortedRows.length === 0)) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Dimension table</CardTitle>
        <CardDescription>
          Granular technical measurements per SIZE / DN row.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {dimsQuery.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : dimsQuery.isError ? (
          <p className="text-sm text-destructive">
            Failed to load dimension table.
          </p>
        ) : sortedColumns.length === 0 || sortedRows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sin tabla dimensional configurada para este producto
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SIZE</TableHead>
                <TableHead>DN</TableHead>
                {showActuationColumn ? (
                  <TableHead>Actuation</TableHead>
                ) : null}
                {sortedColumns.map((col) => (
                  <TableHead key={col.id}>
                    {formatColumnHeader(col)}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRows.map((row) => {
                const cellMap = cellsByRowAndColumn.get(row.id);
                return (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">
                      {row.size_label ?? "—"}
                    </TableCell>
                    <TableCell>
                      {row.dn !== null && row.dn !== undefined
                        ? row.dn
                        : "—"}
                    </TableCell>
                    {showActuationColumn ? (
                      <TableCell>
                        {resolveActuationLabel(
                          row.actuation_code_id,
                          actsQuery.data,
                        )}
                      </TableCell>
                    ) : null}
                    {sortedColumns.map((col) => (
                      <TableCell key={col.id} className="tabular-nums">
                        {renderCellValue(cellMap?.get(col.id), col)}
                      </TableCell>
                    ))}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export default DimensionTable;
