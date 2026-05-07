import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { UserDetailClient } from "./_client";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function UserDetailPage({ params }: PageProps) {
  const { id } = await params;
  const t = await getTranslations("admin.users");

  return (
    <div className="space-y-6 p-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <Button asChild variant="ghost" size="sm">
            <Link href="/admin/usuarios">← {t("backToList")}</Link>
          </Button>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            {t("detailTitle")}
          </h1>
        </div>
      </header>
      <RbacGuard
        permissions={["users:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <UserDetailClient userId={id} />
      </RbacGuard>
    </div>
  );
}
