"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Coins } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { financeApi, type StandardCost } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 4,
  }).format(Number(val));
}

export default function CostosEstandarPage() {
  const { data: costs, isLoading } = useQuery({
    queryKey: ["finance", "standard-costs", CURRENT_YEAR],
    queryFn: () => financeApi.listStandardCosts({ fiscal_year: CURRENT_YEAR }),
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
      <div className="flex items-center gap-3">
        <Coins className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Costos Estándar — FY{CURRENT_YEAR}</h1>
        <Badge variant="outline">{costs?.length ?? 0} registros</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Standard Cost por SKU</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Año Fiscal</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead className="text-right">Costo Estándar</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Vigencia</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(costs ?? []).map((c: StandardCost) => (
                <TableRow key={c.id}>
                  <TableCell className="font-mono text-sm">{c.product_sku}</TableCell>
                  <TableCell>{c.fiscal_year}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{c.cost_type}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-medium">{fmt(c.standard_cost)}</TableCell>
                  <TableCell className="font-mono text-xs">{c.currency}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {c.valid_from} — {c.valid_to ?? "vigente"}
                  </TableCell>
                </TableRow>
              ))}
              {(costs ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    Sin costos estándar para FY{CURRENT_YEAR}
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
