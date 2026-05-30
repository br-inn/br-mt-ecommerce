"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Pencil } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { AuditTimelineRich } from "@/components/domain/audit/audit-timeline-rich";
import { useSupplier } from "@/lib/hooks/suppliers/use-suppliers";
import { useCosts } from "@/lib/hooks/costs/use-costs";
import { costState } from "@/components/domain/costs/cost-state";

interface Props {
  code: string;
}

/**
 * Detalle proveedor — tabs: Datos / Costos asociados / Auditoría.
 * Costos lista los costes donde `supplier_code = code`.
 * Auditoría queda placeholder Sprint 2 (TODO).
 */
export function ProveedorDetail({ code }: Props) {
  const t = useTranslations("proveedores");
  const tTabs = useTranslations("proveedores.tabs");
  const tFields = useTranslations("proveedores.fields");

  const { data: supplier, isLoading, isError, error } = useSupplier(code);

  React.useEffect(() => {
    if (isError && error) toast.error(t("errors.notFound"));
  }, [isError, error, t]);

  if (isLoading) {
    return (
      <div className="space-y-4" data-testid="proveedor-detail-loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-72 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !supplier) {
    return (
      <div
        className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive"
        data-testid="proveedor-detail-error"
      >
        {t("errors.notFound")}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="proveedor-detail-root">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">
              {supplier.code}
            </span>
            <Badge variant={supplier.active ? "default" : "outline"}>
              {supplier.active
                ? t("filters.active")
                : t("filters.inactive")}
            </Badge>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {supplier.name}
          </h1>
        </div>
        <RbacGuard permissions={["suppliers:write"]}>
          <Button asChild variant="outline" size="sm">
            <Link
              href={`/proveedores/${encodeURIComponent(supplier.code)}/editar`}
            >
              <Pencil className="h-4 w-4" /> {t("actions.edit")}
            </Link>
          </Button>
        </RbacGuard>
      </header>

      <Tabs defaultValue="data" className="space-y-4">
        <TabsList>
          <TabsTrigger value="data">{tTabs("data")}</TabsTrigger>
          <TabsTrigger value="costs">{tTabs("costs")}</TabsTrigger>
          <TabsTrigger value="audit">{tTabs("audit")}</TabsTrigger>
        </TabsList>

        <TabsContent value="data">
          <Card>
            <CardHeader>
              <CardTitle>{tTabs("data")}</CardTitle>
              <CardDescription>{supplier.code}</CardDescription>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label={tFields("code")} value={supplier.code} />
                <Row label={tFields("name")} value={supplier.name} />
                <Row
                  label={tFields("contract_currency")}
                  value={supplier.contract_currency}
                />
                <Row
                  label={tFields("lead_time_days")}
                  value={supplier.lead_time_days}
                />
                <Row label={tFields("contact_email")} value={supplier.contact_email} />
                <Row label={tFields("contact_phone")} value={supplier.contact_phone} />
                <Row
                  label={tFields("payment_terms_days")}
                  value={supplier.payment_terms}
                />
                <Row label={tFields("notes")} value={supplier.notes} />
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="costs">
          <SupplierCostsList supplierCode={supplier.code} />
        </TabsContent>

        <TabsContent value="audit">
          <RbacGuard
            permissions={["audit:read"]}
            fallback={
              <Card>
                <CardHeader>
                  <CardTitle>{tTabs("audit")}</CardTitle>
                  <CardDescription>
                    No tienes permiso para ver el historial de auditoría.
                  </CardDescription>
                </CardHeader>
              </Card>
            }
          >
            <AuditTimelineRich
              baseFilters={{
                entity_types: ["supplier"],
                entity_id: supplier.code,
              }}
            />
          </RbacGuard>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground sm:w-44">
        {label}
      </dt>
      <dd className="text-sm font-medium">
        {value === null || value === undefined || value === "" ? "—" : value}
      </dd>
    </div>
  );
}

/** Variante de Badge por estado de vigencia (derivado por fecha). */
const COST_STATE_BADGE: Record<
  ReturnType<typeof costState>,
  "default" | "secondary" | "outline"
> = {
  vigente: "default",
  programado: "secondary",
  caducado: "outline",
};

/** Mini-lista read-only de costes asociados al proveedor (rangos de vigencia). */
function SupplierCostsList({ supplierCode }: { supplierCode: string }) {
  const t = useTranslations("costos");
  const { data, isLoading, isError } = useCosts({ supplier: supplierCode });

  const items = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("tabs.costes")}</CardTitle>
        <CardDescription>{t("empty.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-md" />
            ))}
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("empty.title")}</p>
        ) : (
          <ul className="divide-y">
            {items.map((c) => {
              const state = costState(c);
              return (
                <li
                  key={c.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm"
                >
                  <span className="font-mono text-xs">{c.sku}</span>
                  <span className="font-mono text-xs">{c.scheme_code}</span>
                  <span className="tabular-nums">
                    {c.scheme_landed_aed ?? "—"} AED
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {c.valid_from} → {c.valid_to ?? t("open")}
                  </span>
                  <Badge variant={COST_STATE_BADGE[state]}>
                    {t(`states.${state}`)}
                  </Badge>
                  <Button asChild variant="link" size="sm" className="h-auto p-0">
                    <Link
                      href={`/catalogo/${encodeURIComponent(c.sku)}/costos`}
                    >
                      {t("viewInCosts")}
                    </Link>
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
