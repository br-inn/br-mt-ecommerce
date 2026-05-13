"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { financeApi, type PlLine } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 2,
  }).format(Number(val));
}

export default function PlPage() {
  const [fiscalYear] = React.useState(CURRENT_YEAR);
  const [periodFrom] = React.useState(1);
  const [periodTo] = React.useState(new Date().getMonth() + 1);

  const { data, isLoading } = useQuery({
    queryKey: ["finance", "pl", fiscalYear, periodFrom, periodTo],
    queryFn: () =>
      financeApi.getPl({ fiscal_year: fiscalYear, period_from: periodFrom, period_to: periodTo }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const revenue = data?.revenue_total ?? "0";
  const expenses = data?.expense_total ?? "0";
  const netIncome = data?.net_income ?? "0";
  const netNum = Number(netIncome);

  const revenueLines = (data?.lines ?? []).filter((l: PlLine) => l.account_type === "REVENUE");
  const expenseLines = (data?.lines ?? []).filter((l: PlLine) => l.account_type === "EXPENSE");

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <TrendingUp className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">
          P&amp;L — FY{fiscalYear} (P{periodFrom}–P{periodTo})
        </h1>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Ingresos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-green-600">{fmt(revenue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Gastos</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-red-500">{fmt(expenses)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">Utilidad Neta</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {netNum > 0 ? (
                <TrendingUp className="size-5 text-green-600" />
              ) : netNum < 0 ? (
                <TrendingDown className="size-5 text-red-500" />
              ) : (
                <Minus className="size-5 text-muted-foreground" />
              )}
              <p className={`text-2xl font-bold ${netNum >= 0 ? "text-green-600" : "text-red-500"}`}>
                {fmt(netIncome)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Revenue lines */}
      <Card>
        <CardHeader>
          <CardTitle>Ingresos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cuenta</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead className="text-right">Período</TableHead>
                <TableHead className="text-right">Neto</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {revenueLines.map((l: PlLine) => (
                <TableRow key={`${l.account_code}-${l.posting_period}`}>
                  <TableCell className="font-mono text-xs">{l.account_code}</TableCell>
                  <TableCell>{l.account_name}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">P{l.posting_period}</TableCell>
                  <TableCell className="text-right font-medium text-green-600">{fmt(l.net_amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Expense lines */}
      <Card>
        <CardHeader>
          <CardTitle>Gastos</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Cuenta</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead className="text-right">Período</TableHead>
                <TableHead className="text-right">Neto</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {expenseLines.map((l: PlLine) => (
                <TableRow key={`${l.account_code}-${l.posting_period}`}>
                  <TableCell className="font-mono text-xs">{l.account_code}</TableCell>
                  <TableCell>{l.account_name}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">P{l.posting_period}</TableCell>
                  <TableCell className="text-right font-medium text-red-500">{fmt(l.net_amount)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
