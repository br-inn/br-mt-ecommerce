"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
import { useSupplier } from "@/lib/hooks/suppliers/use-suppliers";
import { SupplierForm } from "../../_components/supplier-form";

interface Props {
  /** PK ahora es `code` (string), no UUID. El nombre `id` se mantiene como
   *  segmento de URL legacy. */
  id: string;
}

export function SupplierDetail({ id }: Props) {
  const t = useTranslations("suppliers");
  const tFields = useTranslations("suppliers.form.fields");
  const router = useRouter();
  const sp = useSearchParams();
  const initialEdit = sp.get("edit") === "1";
  const [editing, setEditing] = React.useState(initialEdit);

  const { data: supplier, isLoading, isError, error } = useSupplier(id);

  React.useEffect(() => {
    if (isError && error) toast.error(t("errors.notFound"));
  }, [isError, error, t]);

  if (isLoading) {
    return (
      <div className="space-y-4" data-testid="supplier-detail-loading">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-72 w-full rounded-lg" />
      </div>
    );
  }

  if (isError || !supplier) {
    return (
      <div
        className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive"
        data-testid="supplier-detail-error"
      >
        {t("errors.notFound")}
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="supplier-detail-root">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">
              {supplier.code}
            </span>
            <Badge variant={supplier.active ? "default" : "outline"}>
              {supplier.active ? t("filters.active") : t("filters.inactive")}
            </Badge>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{supplier.name}</h1>
        </div>
        {!editing ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setEditing(true)}
            data-testid="supplier-edit-toggle"
          >
            <Pencil className="h-4 w-4" /> {t("actions.edit")}
          </Button>
        ) : null}
      </header>

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("editTitle")}</CardTitle>
            <CardDescription>{t("editSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <SupplierForm
              initial={supplier}
              onDone={() => {
                setEditing(false);
                router.replace(`/suppliers/${encodeURIComponent(id)}`);
              }}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{t("infoTitle")}</CardTitle>
            <CardDescription>{t("infoSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <dl>
              <Row label={tFields("code")} value={supplier.code} />
              <Row label={tFields("name")} value={supplier.name} />
              <Row
                label={tFields("contractCurrency")}
                value={supplier.contract_currency}
              />
              <Row
                label={tFields("leadTimeDays")}
                value={supplier.lead_time_days}
              />
              <Row label={tFields("email")} value={supplier.contact_email} />
              <Row label={tFields("phone")} value={supplier.contact_phone} />
              <Row
                label={tFields("paymentTerms")}
                value={supplier.payment_terms}
              />
              <Row label={tFields("notes")} value={supplier.notes} />
            </dl>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
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
