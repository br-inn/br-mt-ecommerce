import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { CompetitorBrandsClient } from "./_client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin.competitorBrands");
  return { title: t("title") };
}

export default async function CompetitorBrandsPage() {
  const t = await getTranslations("admin.competitorBrands");

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("description")}</p>
      </header>

      <RbacGuard
        permissions={["scraper:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <CompetitorBrandsClient />
      </RbacGuard>
    </div>
  );
}
