"use client";

import * as React from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Circle, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { financeApi, type PeriodCloseChecklist } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_PERIOD = new Date().getMonth() + 1;

export default function CierrePage() {
  const qc = useQueryClient();

  const { isLoading } = useQuery({
    queryKey: ["finance", "period-close"],
    queryFn: () => financeApi.listAccounts().then(() => [] as PeriodCloseChecklist[]), // placeholder
  });

  const startClose = useMutation({
    mutationFn: () => financeApi.startPeriodClose(CURRENT_YEAR, CURRENT_PERIOD),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["finance", "period-close"] }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold">Cierre de Período</h1>
        </div>
        <Button
          onClick={() => startClose.mutate()}
          disabled={startClose.isPending}
          size="sm"
        >
          Iniciar Cierre P{CURRENT_PERIOD}/{CURRENT_YEAR}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Checklist de Cierre — FY{CURRENT_YEAR} P{CURRENT_PERIOD}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              "Reconcile AR",
              "Reconcile AP",
              "Post accruals",
              "Run depreciation",
              "FX revaluation",
              "Close subledgers",
              "Review variances",
              "CIT provision",
              "Lock period",
            ].map((item, idx) => (
              <div key={idx} className="flex items-center gap-3 p-2 rounded-md border">
                <Circle className="size-4 text-muted-foreground" />
                <span className="text-sm">{item}</span>
                <Badge variant="secondary" className="ml-auto">Pendiente</Badge>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <AlertTriangle className="size-4 text-yellow-500" />
            Inicia el cierre para activar el checklist interactivo.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
