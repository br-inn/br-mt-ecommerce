import { SeriesSparePartsBrowser } from "@/components/domain/series-spare-parts-browser";

export const dynamic = "force-dynamic";

/**
 * Página Fase 5 — listado de recambios aplicables a una serie.
 *
 * El segmento `[code]` puede ser tanto UUID como código de serie; el endpoint
 * backend `GET /api/v1/series/{series_id}/spare-parts` admite ambos.
 */
export default async function SeriesSparePartsPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Recambios de la serie</h1>
        <p className="text-sm text-muted-foreground">
          Serie: <span className="font-mono">{code}</span>
        </p>
      </header>
      <SeriesSparePartsBrowser seriesId={code} />
    </main>
  );
}
