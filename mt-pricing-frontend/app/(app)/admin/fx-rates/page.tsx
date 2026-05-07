import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { FxRatesAdminClient } from "./_client";

/**
 * `/admin/fx-rates` — lista de FX rates históricos + form modal "Nueva tasa"
 * (US-1A-05-03).
 *
 * RBAC:
 *  - read → `fx:read` (todos los autenticados ven la tabla).
 *  - write → `fx:manage` (TI/admin) — el form sólo se monta para esos roles.
 */
export default async function FxRatesAdminPage() {
  const t = await getTranslations("fx_rates");

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
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
            <FxRatesAdminClient />
          </RbacGuard>
        </CardContent>
      </Card>
    </div>
  );
}
