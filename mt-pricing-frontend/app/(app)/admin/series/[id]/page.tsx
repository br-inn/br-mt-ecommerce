import { RbacGuard } from "@/components/auth/rbac-guard";

import { SeriesDetailClient } from "./_client";

interface PageProps {
  params: Promise<{ id: string }>;
}

/**
 * `/admin/series/{id}` — detalle de serie con 4 tabs:
 *  General · Traducciones · Divisiones · Certificaciones.
 */
export default async function SeriesDetailPage({ params }: PageProps) {
  const { id } = await params;
  return (
    <div className="space-y-6 p-6">
      <RbacGuard
        permissions={["admin:taxonomy"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800">
            No tienes permisos para administrar la taxonomía.
          </div>
        }
      >
        <SeriesDetailClient seriesId={id} />
      </RbacGuard>
    </div>
  );
}
