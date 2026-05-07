import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { JobDetailClient } from "./_client";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function JobDetailPage({ params }: PageProps) {
  const { id } = await params;
  const t = await getTranslations("admin.jobs");

  return (
    <div className="space-y-6 p-6">
      <header>
        <Button asChild variant="ghost" size="sm">
          <Link href="/admin/jobs">← {t("backToList")}</Link>
        </Button>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {t("detailTitle")}
        </h1>
      </header>
      <RbacGuard
        permissions={["jobs:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <JobDetailClient jobId={id} />
      </RbacGuard>
    </div>
  );
}
