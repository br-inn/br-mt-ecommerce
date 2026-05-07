import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { CreateJobClient } from "./_client";

export default async function CreateJobPage() {
  const t = await getTranslations("admin.jobs");

  return (
    <div className="space-y-6 p-6">
      <header>
        <Button asChild variant="ghost" size="sm">
          <Link href="/admin/jobs">← {t("backToList")}</Link>
        </Button>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {t("createTitle")}
        </h1>
        <p className="text-sm text-muted-foreground">{t("createSubtitle")}</p>
      </header>
      <RbacGuard
        permissions={["jobs:write"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <CreateJobClient />
      </RbacGuard>
    </div>
  );
}
