import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { ColaValidacionClient } from "./_client";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("admin.scraper.cola");
  return { title: t("title") };
}

export default async function ColaValidacionPage() {
  const t = await getTranslations("admin.scraper");

  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("cola.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("cola.description")}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/admin/scraper">{t("title")}</Link>
        </Button>
      </header>

      <RbacGuard
        permissions={["products:read"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permiso para ver esta sección.
          </div>
        }
      >
        <ColaValidacionClient />
      </RbacGuard>
    </div>
  );
}
