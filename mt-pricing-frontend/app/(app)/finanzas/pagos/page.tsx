"use client";

import * as React from "react";
import { PiggyBank } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function PagosPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <PiggyBank className="size-5 text-muted-foreground" />
        <h1 className="text-xl font-semibold">Payment Runs</h1>
        <Badge variant="secondary">AP</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Propuestas de Pago a Proveedores</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Usa el API <code className="font-mono text-xs">POST /api/v1/finance/payment-runs</code> para
            generar propuestas automáticas de pago de items vencidos. Las propuestas requieren
            aprobación del rol <strong>gerente</strong> antes de ejecutarse.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
