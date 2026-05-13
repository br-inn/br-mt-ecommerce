"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type FinancialEntry } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

const TYPE_BADGE: Record<string, string> = {
  MANUAL: "default",
  SYSTEM: "secondary",
  REVERSAL: "warning",
  ACCRUAL: "outline",
  FX_REVAL: "secondary",
};

function fmt(val: string | number) {
  return Number(val).toLocaleString("es-AE", { minimumFractionDigits: 2 });
}

export default function AsientosPage() {
  const { data: entries, isLoading } = useQuery({
    queryKey: ["finance", "entries", CURRENT_YEAR],
    queryFn: () =>
      financeApi.listEntries({ fiscal_year: CURRENT_YEAR, limit: 100 }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ScrollText className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Universal Journal — FY{CURRENT_YEAR}</h1>
        <Badge variant="outline">{entries?.length ?? 0} asientos</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Asientos Contables</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>N° Asiento</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Módulo</TableHead>
                <TableHead className="text-right">Debe</TableHead>
                <TableHead className="text-right">Haber</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Descripción</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(entries ?? []).map((e: FinancialEntry) => (
                <TableRow key={e.id} className={e.is_reversed ? "opacity-50" : undefined}>
                  <TableCell className="font-mono text-xs">{e.entry_number}</TableCell>
                  <TableCell className="text-xs">{e.journal_date}</TableCell>
                  <TableCell>
                    <Badge variant={(TYPE_BADGE[e.entry_type] ?? "secondary") as "default" | "secondary" | "outline" | "destructive"}>
                      {e.entry_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{e.source_module ?? "—"}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{fmt(e.debit_amount)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{fmt(e.credit_amount)}</TableCell>
                  <TableCell className="font-mono text-xs">{e.currency_code}</TableCell>
                  <TableCell className="text-xs text-muted-foreground truncate max-w-[200px]">
                    {e.description ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
