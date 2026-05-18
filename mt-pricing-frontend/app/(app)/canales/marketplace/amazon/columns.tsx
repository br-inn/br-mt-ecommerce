"use client";

import * as React from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { AlertCircle, CheckCircle, Loader2, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AmazonListingValidation, AmazonFieldError } from "@/lib/api/endpoints/marketplace-listings";

// ---------------------------------------------------------------------------
// Actions interface injected by the page
// ---------------------------------------------------------------------------

export interface ColumnActions {
  onGenerate: (sku: string) => Promise<void>;
  generatingSkus: Set<string>;
}

// ---------------------------------------------------------------------------
// Issue tooltip (using native title attribute — tooltip.tsx not installed)
// ---------------------------------------------------------------------------

function IssuesSummary({ errors, warnings }: { errors: AmazonFieldError[]; warnings: AmazonFieldError[] }) {
  if (errors.length === 0 && warnings.length === 0) {
    return <span className="text-muted-foreground text-xs">—</span>;
  }

  const lines: string[] = [
    ...errors.map((e) => `✗ [${e.field}] ${e.message}`),
    ...warnings.map((w) => `⚠ [${w.field}] ${w.message}`),
  ];

  return (
    <span
      title={lines.join("\n")}
      className="inline-flex cursor-help items-center gap-1 text-xs text-muted-foreground underline decoration-dotted"
    >
      {errors.length > 0 && (
        <span className="text-destructive font-medium">{errors.length} error{errors.length !== 1 ? "s" : ""}</span>
      )}
      {errors.length > 0 && warnings.length > 0 && <span>/</span>}
      {warnings.length > 0 && (
        <span className="text-amber-500 font-medium">{warnings.length} warning{warnings.length !== 1 ? "s" : ""}</span>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Column builder
// ---------------------------------------------------------------------------

export function buildColumns(actions: ColumnActions): ColumnDef<AmazonListingValidation>[] {
  return [
    {
      accessorKey: "sku",
      header: "SKU",
      cell: ({ row }) => (
        <span className="font-mono text-sm">{row.original.sku}</span>
      ),
    },
    {
      id: "status",
      header: "Estado",
      cell: ({ row }) => {
        const { is_ready, errors } = row.original;
        if (is_ready) {
          return (
            <Badge className="gap-1 border-transparent bg-emerald-500/15 text-emerald-700 dark:text-emerald-400">
              <CheckCircle className="size-3" />
              Listo
            </Badge>
          );
        }
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertCircle className="size-3" />
            {errors.length} error{errors.length !== 1 ? "es" : ""}
          </Badge>
        );
      },
    },
    {
      id: "issues",
      header: "Problemas",
      cell: ({ row }) => (
        <IssuesSummary errors={row.original.errors} warnings={row.original.warnings} />
      ),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => {
        const sku = row.original.sku;
        const isGenerating = actions.generatingSkus.has(sku);
        return (
          <Button
            size="sm"
            variant="outline"
            disabled={isGenerating}
            onClick={() => void actions.onGenerate(sku)}
            className="gap-1.5"
          >
            {isGenerating ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Sparkles className="size-3.5" />
            )}
            {isGenerating ? "Generando…" : "Generar con IA"}
          </Button>
        );
      },
    },
  ];
}
