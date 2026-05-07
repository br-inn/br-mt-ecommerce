"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { type ColumnDef } from "@tanstack/react-table";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/data/data-table";
import { useSuppliers } from "@/lib/hooks/suppliers/use-suppliers";
import {
  type Supplier,
  type SupplierFilters,
} from "@/lib/api/endpoints/suppliers";
import { useSuppliersListFilters } from "./suppliers-filters";
import { SupplierActionsMenu } from "./supplier-actions-menu";

/** Tabla `/suppliers` (legacy). Patrón espejo de products-table. */
export function SuppliersTable() {
  const t = useTranslations("suppliers");
  const tCommon = useTranslations("common");
  const { filters: urlFilters } = useSuppliersListFilters();

  const filters: SupplierFilters = React.useMemo(
    () => ({
      search: urlFilters.search,
      contract_currency: urlFilters.contract_currency,
      active: urlFilters.active,
    }),
    [urlFilters.search, urlFilters.contract_currency, urlFilters.active],
  );

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useSuppliers(filters);

  React.useEffect(() => {
    if (isError && error) {
      toast.error(t("errors.loadFailed"));
    }
  }, [isError, error, t]);

  const items = React.useMemo<Supplier[]>(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  const columns = React.useMemo<ColumnDef<Supplier>[]>(
    () => [
      {
        id: "code",
        header: () => <span>{t("columns.code")}</span>,
        accessorKey: "code",
        cell: ({ row }) => (
          <Link
            href={`/suppliers/${encodeURIComponent(row.original.code)}`}
            className="font-mono text-xs font-semibold text-primary hover:underline"
            data-testid={`supplier-row-${row.original.code}`}
          >
            {row.original.code}
          </Link>
        ),
      },
      {
        id: "name",
        header: () => <span>{t("columns.name")}</span>,
        accessorKey: "name",
        cell: ({ row }) => (
          <span className="line-clamp-1 max-w-xs">{row.original.name}</span>
        ),
      },
      {
        id: "contract_currency",
        header: () => <span>{t("columns.currency")}</span>,
        accessorKey: "contract_currency",
        cell: ({ row }) => row.original.contract_currency,
      },
      {
        id: "leadTime",
        header: () => <span>{t("columns.leadTime")}</span>,
        accessorKey: "lead_time_days",
        cell: ({ row }) =>
          row.original.lead_time_days !== null
            ? t("daysShort", { count: row.original.lead_time_days })
            : "—",
      },
      {
        id: "email",
        header: () => <span>{t("columns.email")}</span>,
        accessorKey: "contact_email",
        cell: ({ row }) => row.original.contact_email ?? "—",
      },
      {
        id: "active",
        header: () => <span>{t("columns.active")}</span>,
        accessorKey: "active",
        cell: ({ row }) => (
          <Badge variant={row.original.active ? "default" : "outline"}>
            {row.original.active ? t("filters.active") : t("filters.inactive")}
          </Badge>
        ),
      },
      {
        id: "actions",
        header: () => <span className="sr-only">{t("columns.actions")}</span>,
        cell: ({ row }) => <SupplierActionsMenu supplier={row.original} />,
      },
    ],
    [t],
  );

  if (isLoading) {
    return (
      <div className="space-y-2" data-testid="suppliers-loading">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card data-testid="suppliers-error">
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <p className="text-sm text-muted-foreground">{t("errors.loadFailed")}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            {tCommon("retry")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (items.length === 0) {
    return (
      <Card data-testid="suppliers-empty">
        <CardContent className="flex flex-col items-center gap-2 py-16 text-center">
          <h2 className="text-lg font-semibold">{t("empty.title")}</h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            {t("empty.description")}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3" data-testid="suppliers-table-root">
      <DataTable<Supplier, unknown> columns={columns} data={items} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span data-testid="suppliers-total-count">
          {t("totalCount", { count: items.length })}
        </span>
        {hasNextPage ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
            data-testid="suppliers-load-more"
          >
            {isFetchingNextPage ? tCommon("loading") : t("loadMore")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
