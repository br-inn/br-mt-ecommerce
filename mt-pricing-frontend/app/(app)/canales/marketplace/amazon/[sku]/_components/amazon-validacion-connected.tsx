"use client";

import * as React from "react";
import { CheckCircle, AlertCircle, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MT } from "@/components/mt/tokens";
import {
  marketplaceListingsApi,
  type AmazonListingValidation,
} from "@/lib/api/endpoints/marketplace-listings";

interface Props {
  sku: string;
}

export function AmazonValidacionConnected({ sku }: Props) {
  const [validation, setValidation] = React.useState<AmazonListingValidation | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setIsLoading(true);
    setError(null);
    marketplaceListingsApi
      .validateSku(sku)
      .then(setValidation)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setIsLoading(false));
  }, [sku]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (!validation) return null;

  return (
    <div className="flex flex-col gap-6">
      {/* ── Estado global ── */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Estado de validación</CardTitle>
          <CardDescription>Resultado del chequeo de campos requeridos para Amazon UAE</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {validation.is_ready ? (
            <div
              className="flex items-center gap-2 rounded-md border px-3 py-2.5 text-[13px]"
              style={{ background: MT.successSoft, borderColor: MT.successBorder, color: MT.success }}
            >
              <CheckCircle className="size-4 shrink-0" />
              <span className="font-medium">Listo para exportar — todos los campos requeridos están completos</span>
            </div>
          ) : null}

          {/* ── Errores ── */}
          {validation.errors.length > 0 ? (
            <div
              className="rounded-md border px-3 py-3 space-y-2"
              style={{ background: MT.dangerSoft, borderColor: MT.dangerBorder }}
            >
              <div
                className="flex items-center gap-2 text-[13px] font-medium"
                style={{ color: MT.danger }}
              >
                <AlertCircle className="size-4 shrink-0" />
                {validation.errors.length} error{validation.errors.length !== 1 ? "es" : ""}
              </div>
              <ul className="ml-6 list-disc space-y-1">
                {validation.errors.map((e, i) => (
                  <li key={i} className="text-[12.5px]" style={{ color: MT.danger }}>
                    <span className="font-semibold">{e.field}:</span> {e.message}
                    {e.code ? (
                      <span className="ml-1.5 font-mono text-[10.5px] opacity-60">[{e.code}]</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* ── Warnings ── */}
          {validation.warnings.length > 0 ? (
            <div
              className="rounded-md border px-3 py-3 space-y-2"
              style={{ background: MT.warningSoft, borderColor: MT.warningBorder }}
            >
              <div
                className="flex items-center gap-2 text-[13px] font-medium"
                style={{ color: MT.warning }}
              >
                <AlertTriangle className="size-4 shrink-0" />
                {validation.warnings.length} alerta{validation.warnings.length !== 1 ? "s" : ""}
              </div>
              <ul className="ml-6 list-disc space-y-1">
                {validation.warnings.map((w, i) => (
                  <li key={i} className="text-[12.5px]" style={{ color: MT.warning }}>
                    <span className="font-semibold">{w.field}:</span> {w.message}
                    {w.code ? (
                      <span className="ml-1.5 font-mono text-[10.5px] opacity-60">[{w.code}]</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {validation.is_ready && validation.warnings.length === 0 ? (
            <p className="text-[12.5px] text-muted-foreground">Sin alertas adicionales.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
