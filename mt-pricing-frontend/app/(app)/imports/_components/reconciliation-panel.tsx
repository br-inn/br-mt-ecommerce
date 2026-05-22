"use client";

import { CheckCircle, AlertTriangle, Download } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Button } from "@/components/ui/button";

export interface ReconciliationResult {
  total_excel_rows: number;
  inserted: number;
  updated: number;
  no_change: number;
  error_rows: number;
  locked_rows: number;
  gap: number;
  is_complete: boolean;
  missing_skus: string[];
}

interface Props {
  reconciliation: ReconciliationResult;
}

export function ReconciliationPanel({ reconciliation }: Props) {
  const {
    is_complete,
    total_excel_rows,
    inserted,
    updated,
    no_change,
    error_rows,
    gap,
    missing_skus,
  } = reconciliation;

  function downloadMissingCsv() {
    const csv = ["sku", ...missing_skus].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "filas-faltantes.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className={cn(
        "mt-4 rounded-md border p-4",
        is_complete
          ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100"
          : "border-destructive/40 bg-destructive/10 text-destructive",
      )}
      data-testid="reconciliation-panel"
    >
      <div className="flex items-start gap-2">
        {is_complete ? (
          <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
        ) : (
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
        )}
        <div className="flex-1">
          <p className="font-semibold text-sm">
            {is_complete
              ? "Carga completa"
              : `Carga incompleta — ${gap} fila${gap !== 1 ? "s" : ""} sin contabilizar`}
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            <li>
              <span className="font-medium">{total_excel_rows}</span> filas en Excel
            </li>
            <li>
              <span className="font-medium text-emerald-700 dark:text-emerald-300">
                {inserted}
              </span>{" "}
              creadas
              {" · "}
              <span className="font-medium">{updated}</span> actualizadas
              {" · "}
              <span className="font-medium opacity-70">{no_change}</span> sin cambios
            </li>
            {error_rows > 0 && (
              <li>
                <span className="font-medium">{error_rows}</span> filas con error
              </li>
            )}
          </ul>
          {!is_complete && missing_skus.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={downloadMissingCsv}
            >
              <Download className="mr-2 h-4 w-4" aria-hidden />
              Descargar CSV de filas faltantes
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
