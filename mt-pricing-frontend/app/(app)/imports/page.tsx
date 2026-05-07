import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { ImportWizard } from "./_components/import-wizard";

/**
 * `/imports` — wizard PIM (US-1A-06-01 frontend half).
 * Pantalla 10 del UX (4 pasos: upload → preview → confirm → progress + report).
 */
export default async function ImportsPage() {
  const t = await getTranslations("imports");

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <RbacGuard
        permissions={["imports:execute"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
            {t("noPermission")}
          </div>
        }
      >
        <ImportWizard />
      </RbacGuard>
    </div>
  );
}
