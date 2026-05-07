import { getTranslations } from "next-intl/server";

import { RbacGuard } from "@/components/auth/rbac-guard";

import { AdminCalibratorClient } from "./_client";

/**
 * `/admin/calibrator` — versión activa del isotonic calibrator + train trigger
 * + lista de versiones con promote (US-1A-DEV-01 frontend / US-1A-09-07).
 *
 * RBAC:
 *  - read    → `admin:read`
 *  - train   → `admin:calibrator:train`
 *  - promote → `admin:calibrator:promote`
 *
 * Backend:
 *  GET  /api/v1/admin/calibrator/active
 *  POST /api/v1/admin/calibrator/train
 *  POST /api/v1/admin/calibrator/promote/{version}
 */
export default async function AdminCalibratorPage() {
  const t = await getTranslations("admin.calibrator");

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>
      <RbacGuard
        permissions={["admin:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            {t("noPermission")}
          </div>
        }
      >
        <AdminCalibratorClient />
      </RbacGuard>
    </div>
  );
}
