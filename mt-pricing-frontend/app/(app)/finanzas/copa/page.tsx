"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type CopaLine } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 0,
  }).format(Number(val));
}

export default function CopaPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["finance", "copa", CURRENT_YEAR],
    queryFn: () => financeApi.getCopa({ fiscal_year: CURRENT_YEAR }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const lines = data?.lines ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <BarChart3 className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">CO-PA — Contribution Margin FY{CURRENT_YEAR}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Margen de Contribución por Profit Center</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Profit Center</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
                <TableHead className="text-right">COGS</TableHead>
                <TableHead className="text-right">Gross Margin</TableHead>
                <TableHead className="text-right">GM%</TableHead>
                <TableHead className="text-right">OpEx</TableHead>
                <TableHead className="text-right font-semibold">EBIT</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {lines.map((l: CopaLine) => (
                <TableRow key={l.profit_center_code}>
                  <TableCell>
                    <div className="font-medium">{l.profit_center_name}</div>
                    <div className="text-xs text-muted-foreground">{l.profit_center_code}</div>
                  </TableCell>
                  <TableCell className="text-right text-green-600">{fmt(l.revenue)}</TableCell>
                  <TableCell className="text-right text-red-500">{fmt(l.cogs)}</TableCell>
                  <TableCell className="text-right font-medium">{fmt(l.gross_margin)}</TableCell>
                  <TableCell className="text-right text-sm text-muted-foreground">
                    {l.gross_margin_pct ? `${l.gross_margin_pct}%` : "—"}
                  </TableCell>
                  <TableCell className="text-right text-red-400">{fmt(l.opex)}</TableCell>
                  <TableCell className={`text-right font-semibold ${Number(l.ebit) >= 0 ? "text-green-700" : "text-red-600"}`}>
                    {fmt(l.ebit)}
                  </TableCell>
                </TableRow>
              ))}
              {lines.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Sin datos de CO-PA para FY{CURRENT_YEAR}
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
