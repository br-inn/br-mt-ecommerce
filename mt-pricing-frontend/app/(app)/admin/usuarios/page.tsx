import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { UsersAdminClient } from "./_client";

/**
 * `/admin/usuarios` — listado paginado + filtros (Server Component).
 * El client component maneja DataTable, search, role filter, active toggle.
 */
export default async function UsuariosAdminPage() {
  const t = await getTranslations("admin.users");

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <RbacGuard permissions={["users:invite"]}>
          <Button asChild>
            <Link href="/admin/usuarios/invitar">{t("inviteCta")}</Link>
          </Button>
        </RbacGuard>
      </header>
      <RbacGuard
        permissions={["users:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <UsersAdminClient />
      </RbacGuard>
    </div>
  );
}
