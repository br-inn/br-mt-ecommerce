import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { ImportRunDetailClient } from "./_client";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ImportRunDetailPage({ params }: PageProps) {
  const { id } = await params;
  const t = await getTranslations("admin.imports");

  return (
    <div className="space-y-6 p-6">
      <header>
        <Button asChild variant="ghost" size="sm">
          <Link href="/admin/imports">← {t("backToList")}</Link>
        </Button>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {t("detailTitle")}
        </h1>
      </header>
      <RbacGuard
        permissions={["imports:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <ImportRunDetailClient runId={id} />
      </RbacGuard>
    </div>
  );
}
