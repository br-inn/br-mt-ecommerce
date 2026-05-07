/**
 * `/precios` — listado de prices con filtros (Wave 2 motor v5.1).
 *
 * Filtros: SKU, channel_code, scheme_code, status. Cursor pagination cliente.
 * Patrón espejo de `/suppliers` y `/products`.
 */
"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  pricingApi,
  type PriceRow,
  type PriceStatus,
} from "@/lib/api/endpoints/pricing";

const STATUS_BADGE: Record<PriceStatus, { variant: string; label: string }> = {
  draft: { variant: "secondary", label: "Borrador" },
  pending_review: { variant: "warning", label: "Pendiente revisión" },
  auto_approved: { variant: "default", label: "Auto-aprobado" },
  approved: { variant: "success", label: "Aprobado" },
  rejected: { variant: "destructive", label: "Rechazado" },
  revised: { variant: "secondary", label: "Revisado" },
  exported: { variant: "outline", label: "Exportado" },
  superseded: { variant: "outline", label: "Reemplazado" },
  migrated: { variant: "outline", label: "Migrado" },
};

export default function PricesPage() {
  const t = useTranslations("pricing");
  const [sku, setSku] = React.useState<string>("");
  const [channel, setChannel] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<PriceStatus | "">("");

  const filters = React.useMemo(
    () => ({
      sku: sku || undefined,
      channel: channel || undefined,
      status: (statusFilter || undefined) as PriceStatus | undefined,
      include_total: true,
      limit: 50,
    }),
    [sku, channel, statusFilter],
  );

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["prices", filters],
    queryFn: () => pricingApi.list(filters),
  });

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/precios/simular">{t("simulate.cta")}</Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/precios/aprobaciones">{t("approvals.cta")}</Link>
          </Button>
        </div>
      </header>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 pt-6">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              SKU
            </label>
            <Input
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="4222015"
              className="w-40"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t("filters.channel")}
            </label>
            <Input
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              placeholder="amazon_uae"
              className="w-44"
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {t("filters.status")}
            </label>
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as PriceStatus | "")}
            >
              <option value="">{t("filters.all")}</option>
              {Object.entries(STATUS_BADGE).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>
          <Button variant="ghost" onClick={() => refetch()}>
            {t("filters.refresh")}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>{t("columns.scheme")}</TableHead>
                <TableHead>{t("columns.amount")}</TableHead>
                <TableHead>{t("columns.margin")}</TableHead>
                <TableHead>{t("columns.rule")}</TableHead>
                <TableHead>{t("columns.status")}</TableHead>
                <TableHead>{t("columns.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="text-destructive">
                    {t("errors.loadFailed")}
                  </TableCell>
                </TableRow>
              )}
              {!isLoading && !isError && (data?.items ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="text-muted-foreground">
                    {t("empty")}
                  </TableCell>
                </TableRow>
              )}
              {(data?.items ?? []).map((p: PriceRow) => {
                const meta = STATUS_BADGE[p.status];
                return (
                  <TableRow key={p.id}>
                    <TableCell className="font-mono text-xs">
                      <Link
                        href={`/precios/${p.id}`}
                        className="text-primary hover:underline"
                      >
                        {p.product_sku}
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs">{p.scheme_code}</TableCell>
                    <TableCell className="font-mono">
                      {p.amount} {p.currency}
                    </TableCell>
                    <TableCell>
                      {(Number(p.margin_pct) * 100).toFixed(2)}%
                    </TableCell>
                    <TableCell className="text-xs">
                      {p.rule_applied ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={meta.variant as never}>{meta.label}</Badge>
                    </TableCell>
                    <TableCell>
                      <Button asChild size="sm" variant="ghost">
                        <Link href={`/precios/${p.id}`}>{t("columns.view")}</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
