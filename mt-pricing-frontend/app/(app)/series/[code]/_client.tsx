"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { MtButton, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { seriesApi, type Series, type SeriesTranslation } from "@/lib/api/endpoints/series";
import { seriesTiersApi, type SeriesTier } from "@/lib/api/endpoints/series-tiers";
import { productsApi, type ProductListItem } from "@/lib/api/endpoints/products";

interface Props {
  code: string;
}

export function SeriesLanding({ code }: Props) {
  const allQ = useQuery({
    queryKey: ["series", "public", "list"],
    queryFn: () => seriesApi.listPublic({}),
    staleTime: 60_000,
  });

  const series: Series | undefined = React.useMemo(
    () => allQ.data?.find((s) => s.code === code),
    [allQ.data, code],
  );

  const tiersQ = useQuery({
    queryKey: ["series-tiers", "public"],
    queryFn: () => seriesTiersApi.list(),
    staleTime: 5 * 60_000,
  });

  const trQ = useQuery({
    queryKey: ["series", series?.id, "translations"],
    queryFn: () => seriesApi.listTranslationsPublic(series!.id),
    enabled: !!series,
    staleTime: 60_000,
  });

  const productsQ = useQuery({
    queryKey: ["products", "by-series", series?.id],
    queryFn: () => productsApi.list({ series_id: series!.id, limit: 50 }),
    enabled: !!series,
    staleTime: 30_000,
  });

  if (allQ.isLoading) {
    return (
      <div className="p-6 text-sm" style={{ color: MT.ink3 }}>
        Cargando serie…
      </div>
    );
  }

  if (!series) {
    return (
      <div className="p-6">
        <h1 className="text-lg font-semibold" style={{ color: MT.ink }}>
          Serie no encontrada
        </h1>
        <p className="mt-2 text-sm" style={{ color: MT.ink3 }}>
          Código: <code className="mt-mono">{code}</code>
        </p>
        <MtButton asChild className="mt-4">
          <Link href="/catalogo">Volver al catálogo</Link>
        </MtButton>
      </div>
    );
  }

  const tier: SeriesTier | undefined = tiersQ.data?.find((t) => t.id === series.tier_id);
  const trEs: SeriesTranslation | undefined = trQ.data?.find((t) => t.lang === "es");
  const displayName = trEs?.name ?? series.name_en;
  const description = trEs?.description ?? series.description_en ?? "";
  const bullets = trEs?.bullets?.length ? trEs.bullets : series.bullets_en;
  const products: ProductListItem[] = productsQ.data?.items ?? [];

  return (
    <div className="flex flex-col">
      {/* Hero banner */}
      <div
        className="relative overflow-hidden border-b px-6 py-10"
        style={{
          background: series.banner_color ?? "linear-gradient(135deg, #0a4d8c 0%, #1a6ab0 100%)",
          borderColor: MT.border,
        }}
      >
        <div className="relative z-10 flex flex-col gap-3 text-white">
          <div className="flex flex-wrap items-center gap-2">
            {tier && (
              <span
                className="rounded-md px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide"
                style={{
                  background: tier.display_color ?? "#666",
                  color: "#fff",
                }}
              >
                {tier.name}
              </span>
            )}
            {series.pressure_rating_pn !== null && (
              <Pill className="bg-white/20 text-white">PN{series.pressure_rating_pn}</Pill>
            )}
            {(series.temperature_min_c !== null || series.temperature_max_c !== null) && (
              <Pill className="bg-white/20 text-white">
                {series.temperature_min_c ?? "–"}°C / {series.temperature_max_c ?? "–"}°C
              </Pill>
            )}
            {series.features_tags.map((t) => (
              <Pill key={t} className="bg-white/15 uppercase text-white">
                {t}
              </Pill>
            ))}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">{displayName}</h1>
          {description && <p className="max-w-3xl text-sm opacity-95">{description}</p>}
          {series.hero_image_url && (
            <img
              src={series.hero_image_url}
              alt={displayName}
              className="absolute right-6 top-6 hidden h-28 w-28 rounded-xl object-cover ring-2 ring-white/30 md:block"
            />
          )}
        </div>
      </div>

      {/* Bullets */}
      {bullets.length > 0 && (
        <div className="border-b px-6 py-5" style={{ borderColor: MT.border }}>
          <h2 className="mb-3 text-[12px] uppercase tracking-wide" style={{ color: MT.ink4 }}>
            Características
          </h2>
          <ul className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {bullets.map((b) => (
              <li key={b} className="flex items-start gap-2 text-sm" style={{ color: MT.ink2 }}>
                <span className="mt-1 size-1.5 shrink-0 rounded-full bg-mt-accent" />
                {b}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Productos en esta serie */}
      <div className="px-6 py-6">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-lg font-semibold" style={{ color: MT.ink }}>
            Productos en esta serie
          </h2>
          <span className="text-xs" style={{ color: MT.ink4 }}>
            {productsQ.isLoading ? "Cargando…" : `${products.length} elementos`}
          </span>
        </div>
        {products.length === 0 && !productsQ.isLoading ? (
          <div className="text-sm" style={{ color: MT.ink3 }}>
            No hay productos asignados a esta serie todavía.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {products.map((p) => (
              <Link
                key={p.sku}
                href={`/catalogo/${encodeURIComponent(p.sku)}`}
                className="rounded-lg border p-3 transition-colors hover:bg-mt-surface-2"
                style={{ borderColor: MT.border }}
              >
                <div className="flex items-start gap-3">
                  {p.primary_image_url ? (
                    <img
                      src={p.primary_image_url}
                      alt={p.name_en}
                      className="size-14 shrink-0 rounded object-cover"
                    />
                  ) : (
                    <div className="size-14 shrink-0 rounded bg-mt-surface-2" />
                  )}
                  <div className="min-w-0">
                    <div
                      className="mt-mono truncate text-[12px]"
                      style={{ color: MT.ink3 }}
                    >
                      {p.sku}
                    </div>
                    <div
                      className="mt-0.5 truncate text-sm font-medium"
                      style={{ color: MT.ink }}
                    >
                      {p.name_en}
                    </div>
                    {p.dn && (
                      <div className="mt-1 text-xs" style={{ color: MT.ink4 }}>
                        {p.dn} · {p.pn ?? ""}
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
