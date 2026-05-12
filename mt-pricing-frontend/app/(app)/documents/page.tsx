import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DocumentsBrowser } from "@/components/domain/documents-browser";

/**
 * `/documents` — Fase 4 catálogo global de documentos controlados.
 *
 * RBAC: lectura requiere `documents:read` (alineado con admin de assets).
 * El listado es client-side a través de `<DocumentsBrowser>` con filtros
 * por tipo + idioma.
 */
export default function DocumentsPage() {
  return (
    <div className="space-y-6 p-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Documentos</h1>
        <p className="text-sm text-muted-foreground">
          Catálogo global de fichas técnicas, manuales, declaraciones CE,
          certificados y catálogos. Filtra por tipo e idioma.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Browser</CardTitle>
          <CardDescription>
            Documentos versionados con metadatos de emisión.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RbacGuard
            permissions={["documents:read"]}
            fallback={
              <p className="text-sm text-muted-foreground">
                No tienes permisos para listar documentos.
              </p>
            }
          >
            <DocumentsBrowser />
          </RbacGuard>
        </CardContent>
      </Card>
    </div>
  );
}
