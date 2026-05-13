"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Receipt } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type BudgetVsActualLine } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_PERIOD = new Date().getMonth() + 1;

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 2,
  }).format(Number(val));
}

function varianceColor(val: string | number) {
  const n = Number(val);
  if (n > 0) return "text-green-600";
  if (n < 0) return "text-red-500";
  return "text-muted-foreground";
}

export default function PresupuestosPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["finance", "budget-vs-actual", CURRENT_YEAR, CURRENT_PERIOD],
    queryFn: () =>
      financeApi.getBudgetVsActual({ fiscal_year: CURRENT_YEAR, period: CURRENT_PERIOD }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const lines = data?.lines ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Receipt className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">
          Presupuesto vs Real — FY{CURRENT_YEAR} P{CURRENT_PERIOD}
        </h1>
      </div>

      {data && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">Presupuesto</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-bold">{fmt(data.total_budget)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">Real</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-bold">{fmt(data.total_actual)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">Varianza</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-xl font-bold ${varianceColor(data.total_variance)}`}>
                {fmt(data.total_variance)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Detalle por Cuenta</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cuenta</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>PC</TableHead>
                <TableHead className="text-right">Presupuesto</TableHead>
                <TableHead className="text-right">Real</TableHead>
                <TableHead className="text-right">Varianza</TableHead>
                <TableHead className="text-right">Var %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((l: BudgetVsActualLine, idx: number) => (
                <TableRow key={idx}>
                  <TableCell className="font-mono text-xs">{l.account_code}</TableCell>
                  <TableCell className="text-sm">{l.account_name}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{l.profit_center_code ?? "—"}</TableCell>
                  <TableCell className="text-right">{fmt(l.budget)}</TableCell>
                  <TableCell className="text-right">{fmt(l.actual)}</TableCell>
                  <TableCell className={`text-right font-medium ${varianceColor(l.variance)}`}>
                    {fmt(l.variance)}
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {l.variance_pct ? `${l.variance_pct}%` : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {lines.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Sin presupuestos cargados para este período
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
