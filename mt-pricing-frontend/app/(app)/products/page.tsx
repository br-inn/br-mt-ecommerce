import { Suspense } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { FileUp, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { ProductsTable } from "./_components/products-table";
import { ProductsToolbar } from "./_components/products-toolbar";

/**
 * Pantalla 2 — Listado de productos (US-1A-02-03-S1).
 *
 * Server component que pinta el chrome (header, CTA, filtros) y delega la
 * tabla al client component. La tabla consume `GET /api/v1/products` vía
 * `useProducts` (TanStack Query, paginación cursor).
 */
export default async function ProductsPage() {
  const t = await getTranslations("catalog");

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <RbacGuard permissions={["imports:execute"]}>
            <Button variant="outline" disabled aria-disabled title="Sprint 2">
              <FileUp className="h-4 w-4" /> {t("importPim")}
            </Button>
          </RbacGuard>
          <RbacGuard permissions={["products:write"]}>
            <Button asChild>
              <Link href="/catalogo/nuevo">
                <Plus className="h-4 w-4" /> {t("newSku")}
              </Link>
            </Button>
          </RbacGuard>
        </div>
      </header>

      <Suspense fallback={<Skeleton className="h-10 w-full max-w-3xl" />}>
        <ProductsToolbar />
      </Suspense>

      <Suspense
        fallback={
          <div className="space-y-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-md" />
            ))}
          </div>
        }
      >
        <ProductsTable />
      </Suspense>
    </div>
  );
}
