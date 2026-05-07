import { Suspense } from "react";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { SuppliersTable } from "./_components/suppliers-table";
import { SuppliersToolbar } from "./_components/suppliers-toolbar";

/**
 * `/suppliers` — listado CRUD (US-1A-03-02 frontend half).
 * Patrón visual confirmado por humano: reusar Pantalla 2 (`/products`).
 */
export default async function SuppliersPage() {
  const t = await getTranslations("suppliers");

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <RbacGuard permissions={["suppliers:write"]}>
          <Button asChild>
            <Link href="/suppliers/new">
              <Plus className="h-4 w-4" /> {t("new")}
            </Link>
          </Button>
        </RbacGuard>
      </header>

      <Suspense fallback={<Skeleton className="h-10 w-full max-w-3xl" />}>
        <SuppliersToolbar />
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
        <SuppliersTable />
      </Suspense>
    </div>
  );
}
