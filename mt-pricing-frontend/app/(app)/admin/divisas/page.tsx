import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { CurrencyTable } from "@/components/admin/currency-table";

/**
 * `/admin/divisas` — admin completo de currencies (US-1A-05-01-S3).
 *
 * S3 separa el admin en 2 rutas:
 *  - `/admin/divisas`   → CurrencyTable (activate/deactivate, RBAC, audit).
 *  - `/admin/fx-rates`  → tabla histórica + form modal (US-1A-05-03).
 *
 * RBAC: la lectura requiere `fx:read`; el activate/deactivate requiere
 * `currencies:manage` (TI/admin). El render es server-side; el control
 * granular ocurre en `<CurrencyTable>` con `<RbacGuard>`.
 */
export default async function DivisasPage() {
  const t = await getTranslations("currencies");
  const tNav = await getTranslations("admin.nav");

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <RbacGuard permissions={["fx:read"]}>
          <Button asChild variant="outline">
            <Link href="/admin/fx-rates">{tNav("goToFxRates")}</Link>
          </Button>
        </RbacGuard>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("section.tableTitle")}</CardTitle>
          <CardDescription>{t("section.tableDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          <RbacGuard
            permissions={["fx:read"]}
            fallback={
              <p className="text-sm text-muted-foreground">
                {t("rbac.readDenied")}
              </p>
            }
          >
            <CurrencyTable />
          </RbacGuard>
        </CardContent>
      </Card>
    </div>
  );
}
