"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Timer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type PostingPeriod } from "@/lib/api/endpoints/finance";

const CURRENT_YEAR = new Date().getFullYear();

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  open: "default",
  closed: "secondary",
  locked: "destructive",
};

export default function PeriodosPage() {
  const { data: periods, isLoading } = useQuery({
    queryKey: ["finance", "posting-periods", CURRENT_YEAR],
    queryFn: () => financeApi.listPostingPeriods({ fiscal_year: CURRENT_YEAR }),
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
        <Timer className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Períodos Contables — FY{CURRENT_YEAR}</h1>
        <Badge variant="outline">{periods?.length ?? 0} períodos</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Calendario Fiscal</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>P#</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Desde</TableHead>
                <TableHead>Hasta</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead>Cerrado el</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(periods ?? []).map((p: PostingPeriod) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-sm">{p.period_num}</TableCell>
                  <TableCell>{p.period_name ?? `P${p.period_num}`}</TableCell>
                  <TableCell className="text-xs">{p.date_from}</TableCell>
                  <TableCell className="text-xs">{p.date_to}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[p.status] ?? "secondary"}>
                      {p.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {p.closed_at ? new Date(p.closed_at).toLocaleDateString("es-AE") : "—"}
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
