import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { JobsListClient } from "./_client";

export default async function JobsAdminPage() {
  const t = await getTranslations("admin.jobs");

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <RbacGuard permissions={["jobs:write"]}>
          <Button asChild>
            <Link href="/admin/jobs/nuevo">{t("createCta")}</Link>
          </Button>
        </RbacGuard>
      </header>
      <RbacGuard
        permissions={["jobs:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <JobsListClient />
      </RbacGuard>
    </div>
  );
}
