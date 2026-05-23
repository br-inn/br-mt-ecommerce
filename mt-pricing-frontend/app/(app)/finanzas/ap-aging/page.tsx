"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type ApAgingBucket } from "@/lib/api/endpoints/finance";

function fmt(val: string | number) {
  return new Intl.NumberFormat("es-AE", {
    style: "currency", currency: "AED", minimumFractionDigits: 2,
  }).format(Number(val));
}

export default function ApAgingPage() {
  const today = new Date().toISOString().split("T")[0]!;

  const { data, isLoading } = useQuery({
    queryKey: ["finance", "ap-aging", today],
    queryFn: () => financeApi.getApAging({ as_of_date: today }),
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const buckets: ApAgingBucket[] = data?.buckets ?? [];
  const totalAll = buckets.reduce((s: number, b: ApAgingBucket) => s + Number(b.total), 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ClipboardList className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">AP Aging — {data?.as_of_date ?? today}</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Aging por Proveedor</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Proveedor</TableHead>
                <TableHead className="text-right">Corriente</TableHead>
                <TableHead className="text-right">1–30 días</TableHead>
                <TableHead className="text-right">31–60 días</TableHead>
                <TableHead className="text-right">61–90 días</TableHead>
                <TableHead className="text-right">+90 días</TableHead>
                <TableHead className="text-right font-semibold">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {buckets.map((b: ApAgingBucket) => (
                <TableRow key={b.vendor_id}>
                  <TableCell className="font-medium">{b.vendor_id}</TableCell>
                  <TableCell className="text-right text-sm">{fmt(b.current)}</TableCell>
                  <TableCell className="text-right text-sm">{fmt(b.days_1_30)}</TableCell>
                  <TableCell className="text-right text-sm text-yellow-600">{fmt(b.days_31_60)}</TableCell>
                  <TableCell className="text-right text-sm text-orange-500">{fmt(b.days_61_90)}</TableCell>
                  <TableCell className="text-right text-sm text-red-600">{fmt(b.days_90_plus)}</TableCell>
                  <TableCell className="text-right font-semibold">{fmt(b.total)}</TableCell>
                </TableRow>
              ))}
              {buckets.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    Sin items abiertos
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
          {buckets.length > 0 && (
            <div className="flex justify-end mt-4 font-semibold text-sm">
              Total: {fmt(totalAll)}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
