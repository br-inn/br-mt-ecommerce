"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProductCertificates } from "@/lib/hooks/products/use-product-model";
import type { CertificateItem } from "@/lib/api/endpoints/products";

const STATUS_CLASSES: Record<string, string> = {
  valid: "border-green-300 bg-green-50 text-green-700",
  expiring_soon: "border-yellow-300 bg-yellow-50 text-yellow-700",
  critical: "border-orange-300 bg-orange-50 text-orange-700",
  expired: "border-red-300 bg-red-50 text-red-700",
  renewing: "border-blue-300 bg-blue-50 text-blue-700",
};

function StatusBadge({ status }: { status: CertificateItem["status"] }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${STATUS_CLASSES[status] ?? ""}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { year: "numeric", month: "short" });
}

export function ProductCertificates({ sku }: { sku: string }) {
  const { data: certs, isLoading } = useProductCertificates(sku);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!certs?.length) return null;

  return (
    <section aria-label="Certificados" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Certificados
      </h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium">Número</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Emisor</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Emisión</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Vencimiento</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {certs.map((c) => (
              <tr key={c.id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{c.cert_number}</td>
                <td className="px-3 py-2 text-xs">{c.issuer ?? "—"}</td>
                <td className="px-3 py-2 text-xs">{fmtDate(c.issued_at)}</td>
                <td className="px-3 py-2 text-xs">{fmtDate(c.expires_at)}</td>
                <td className="px-3 py-2"><StatusBadge status={c.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
