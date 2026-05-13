"use client";

import { useState } from "react";
import { Globe, Plus, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { productsApi } from "@/lib/api/endpoints/products";
import type { ProductRelease, ReleaseStatus } from "@/lib/api/endpoints/products";

// SAP Fiori Semantic Colors para release status
const RELEASE_STATUS_CONFIG: Record<
  ReleaseStatus,
  { label: string; icon: React.ElementType; className: string }
> = {
  draft:        { label: "Borrador",      icon: AlertCircle,  className: "text-muted-foreground" },
  active:       { label: "Activo",        icon: CheckCircle2, className: "text-green-600" },
  suspended:    { label: "Suspendido",    icon: XCircle,      className: "text-yellow-600" },
  discontinued: { label: "Discontinuado", icon: XCircle,      className: "text-red-600" },
};

const MARKET_FLAGS: Record<string, string> = {
  UAE: "🇦🇪",
  KSA: "🇸🇦",
  MX:  "🇲🇽",
  ES:  "🇪🇸",
  US:  "🇺🇸",
  EU:  "🇪🇺",
};

function ReleaseStatusIcon({ status }: { status: ReleaseStatus }) {
  const cfg = RELEASE_STATUS_CONFIG[status] ?? RELEASE_STATUS_CONFIG.draft;
  const Icon = cfg.icon;
  return (
    <span className={`flex items-center gap-1 text-sm font-medium ${cfg.className}`}>
      <Icon className="h-4 w-4" />
      {cfg.label}
    </span>
  );
}

interface Props {
  sku: string;
}

export function MercadosClient({ sku }: Props) {
  const queryClient = useQueryClient();
  const [activating, setActivating] = useState<string | null>(null);

  const { data: releases, isLoading, isError } = useQuery({
    queryKey: ["product-releases", sku],
    queryFn: () => productsApi.listReleases(sku),
  });

  const activateMutation = useMutation({
    mutationFn: (marketCode: string) => productsApi.activateRelease(sku, marketCode),
    onMutate: (mc) => setActivating(mc),
    onSettled: () => {
      setActivating(null);
      void queryClient.invalidateQueries({ queryKey: ["product-releases", sku] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (marketCode: string) => productsApi.deactivateRelease(sku, marketCode),
    onMutate: (mc) => setActivating(mc),
    onSettled: () => {
      setActivating(null);
      void queryClient.invalidateQueries({ queryKey: ["product-releases", sku] });
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6 text-sm text-destructive">
          Error cargando releases.
        </CardContent>
      </Card>
    );
  }

  const activeCount = releases?.filter((r) => r.is_active).length ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            Releases por Mercado
          </CardTitle>
          <CardDescription>
            Configuración del producto por entidad legal / mercado.{" "}
            <span className="font-medium text-foreground">
              {activeCount} mercado{activeCount !== 1 ? "s" : ""} activo{activeCount !== 1 ? "s" : ""}
            </span>
          </CardDescription>
        </div>
        <RbacGuard permissions={["products:write"]}>
          <Button variant="outline" size="sm" disabled>
            <Plus className="h-4 w-4" /> Agregar mercado
          </Button>
        </RbacGuard>
      </CardHeader>

      <CardContent>
        {!releases || releases.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <Globe className="h-8 w-8 opacity-30" />
            <p className="text-sm">
              Este producto aún no tiene releases configurados para ningún mercado.
            </p>
            <p className="text-xs">
              Los releases controlan precio local, impuesto y activación por país.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mercado</TableHead>
                <TableHead>Nombre local</TableHead>
                <TableHead>SKU local</TableHead>
                <TableHead className="text-right">Precio</TableHead>
                <TableHead>Clase fiscal</TableHead>
                <TableHead>Estado</TableHead>
                <RbacGuard permissions={["products:write"]}>
                  <TableHead className="text-right">Acciones</TableHead>
                </RbacGuard>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.map((release: ProductRelease) => {
                const flag = MARKET_FLAGS[release.market_code] ?? "🌐";
                const isProcessing = activating === release.market_code;
                return (
                  <TableRow key={release.id}>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-1.5">
                        <span>{flag}</span>
                        <span>{release.market_code}</span>
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      {release.local_name ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {release.local_sku ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {release.list_price != null ? (
                        <span>
                          {release.list_price.toLocaleString()}{" "}
                          <span className="text-muted-foreground">
                            {release.price_currency ?? ""}
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {release.tax_class ? (
                        <Badge variant="outline" className="font-mono text-xs">
                          {release.tax_class}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <ReleaseStatusIcon status={release.status} />
                    </TableCell>
                    <RbacGuard permissions={["products:write"]}>
                      <TableCell className="text-right">
                        {release.is_active ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => deactivateMutation.mutate(release.market_code)}
                          >
                            Suspender
                          </Button>
                        ) : (
                          <Button
                            variant="default"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => activateMutation.mutate(release.market_code)}
                          >
                            Activar
                          </Button>
                        )}
                      </TableCell>
                    </RbacGuard>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
