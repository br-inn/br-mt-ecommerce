import { RbacGuard } from "@/components/auth/rbac-guard";

import { TaxonomyAdminClient } from "./_client";

interface PageProps {
  params: Promise<{ slug: string }>;
}

/**
 * `/admin/taxonomies/[slug]` — admin page genérica data-driven.
 *
 * Reemplaza las páginas legacy específicas (`/admin/divisions`,
 * `/admin/series`, etc.) renderizando un CRUD de nodos basado en
 * los metadatos del `TaxonomyType` (label_i18n, is_hierarchical,
 * is_system, ui_layout).
 *
 * RBAC:
 *  - read  → `admin:taxonomy`
 *  - write → `admin:taxonomy`
 */
export default async function TaxonomyAdminPage({ params }: PageProps) {
  const { slug } = await params;

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
        <TaxonomyAdminClient typeSlug={slug} />
      </RbacGuard>
    </div>
  );
}
