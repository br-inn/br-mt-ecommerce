"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { financeApi, type BalanceSheetLine } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 2,
  }).format(Number(val));
}

const TYPE_COLOR: Record<string, string> = {
  ASSET: "text-blue-600",
  LIABILITY: "text-orange-500",
  EQUITY: "text-green-600",
};

export default function BalancePage() {
  const period = new Date().getMonth() + 1;

  const { data, isLoading } = useQuery({
    queryKey: ["finance", "balance-sheet", CURRENT_YEAR, period],
    queryFn: () =>
      financeApi.getBalanceSheet({ fiscal_year: CURRENT_YEAR, as_of_period: period }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const lines = data?.lines ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">
          Balance Sheet — FY{CURRENT_YEAR} hasta P{period}
        </h1>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Activos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-blue-600">{fmt(data?.total_assets ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Pasivos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-orange-500">{fmt(data?.total_liabilities ?? 0)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Patrimonio</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xl font-bold text-green-600">{fmt(data?.total_equity ?? 0)}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Detalle</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cuenta</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Saldo</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((l: BalanceSheetLine) => (
                <TableRow key={l.account_code}>
                  <TableCell className="font-mono text-xs">{l.account_code}</TableCell>
                  <TableCell>{l.account_name}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{l.account_type}</Badge>
                  </TableCell>
                  <TableCell className={`text-right font-medium ${TYPE_COLOR[l.account_type] ?? ""}`}>
                    {fmt(l.balance)}
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
