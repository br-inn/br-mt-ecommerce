"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Boxes } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { inventoryApi } from "@/lib/api/endpoints/inventory";

function fmtAED(value: string): string {
  return `AED ${parseFloat(value).toLocaleString("en-AE", { minimumFractionDigits: 2 })}`;
}

export function InventoryKpiWidget() {
  const { data, isLoading } = useQuery({
    queryKey: ["inventory-summary"],
    queryFn: () => inventoryApi.getSummary(),
    staleTime: 60_000,
  });

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Boxes className="size-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold tracking-tight text-muted-foreground uppercase">
            Inventario
          </h2>
        </div>
        <Link
          href="/inventario"
          className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
        >
          Ver todo <ArrowRight className="size-3" />
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {/* SKUs con stock */}
        <Card>
          <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              SKUs con stock
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              <p className="text-2xl font-semibold tabular-nums">
                {data?.total_skus_with_stock ?? 0}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Valor inventario */}
        <Card>
          <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              Valor inventario
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {isLoading ? (
              <Skeleton className="h-7 w-28" />
            ) : (
              <p className="text-lg font-semibold tabular-nums">
                {data ? fmtAED(data.total_stock_value_aed) : "AED 0.00"}
              </p>
            )}
          </CardContent>
        </Card>

        {/* SKUs sin coste */}
        <Card>
          <CardHeader className="pb-1 pt-3 px-4">
            <CardTitle className="text-xs font-medium text-muted-foreground">
              SKUs sin coste
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-3">
            {isLoading ? (
              <Skeleton className="h-7 w-10" />
            ) : (
              <p
                className={`text-2xl font-semibold tabular-nums ${
                  (data?.skus_without_cost ?? 0) > 0 ? "text-red-600" : ""
                }`}
              >
                {data?.skus_without_cost ?? 0}
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
