import { Suspense } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { ProveedoresTable } from "./_components/proveedores-table";
import { ProveedoresToolbar } from "./_components/proveedores-toolbar";

/**
 * `/proveedores` — listado CRUD master de proveedores (Wave 2A).
 * Server Component shell + Client Components con TanStack Query.
 */
export default async function ProveedoresPage() {
  const t = await getTranslations("proveedores");

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <RbacGuard permissions={["suppliers:write"]}>
          <Button asChild>
            <Link href="/proveedores/nuevo">
              <Plus className="h-4 w-4" /> {t("newButton")}
            </Link>
          </Button>
        </RbacGuard>
      </header>

      <Suspense fallback={<Skeleton className="h-10 w-full max-w-3xl" />}>
        <ProveedoresToolbar />
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
        <ProveedoresTable />
      </Suspense>
    </div>
  );
}
