"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Layers, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { financeApi, type GlAccount } from "@/lib/api/endpoints/finance";

const TYPE_VARIANTS: Record<string, string> = {
  ASSET: "default",
  LIABILITY: "secondary",
  EQUITY: "outline",
  REVENUE: "success",
  EXPENSE: "destructive",
  CONTRA: "warning",
};

export default function CuentasPage() {
  const { data: accounts, isLoading } = useQuery({
    queryKey: ["finance", "accounts"],
    queryFn: () => financeApi.listAccounts(),
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
        <Layers className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Plan de Cuentas (CoA)</h1>
        <Badge variant="outline">{accounts?.length ?? 0} cuentas</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Catálogo de Cuentas Contables</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Código</TableHead>
                <TableHead>Nombre</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Moneda</TableHead>
                <TableHead>Estado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(accounts ?? []).map((acct: GlAccount) => (
                <TableRow key={acct.id}>
                  <TableCell className="font-mono text-sm">{acct.account_code}</TableCell>
                  <TableCell>{acct.account_name}</TableCell>
                  <TableCell>
                    <Badge variant={(TYPE_VARIANTS[acct.account_type] ?? "secondary") as "default" | "secondary" | "outline" | "destructive"}>
                      {acct.account_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{acct.currency}</TableCell>
                  <TableCell>
                    {acct.is_blocked ? (
                      <span className="flex items-center gap-1 text-xs text-red-500">
                        <Lock className="size-3" /> Bloqueada
                      </span>
                    ) : (
                      <span className="text-xs text-green-600">Activa</span>
                    )}
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
