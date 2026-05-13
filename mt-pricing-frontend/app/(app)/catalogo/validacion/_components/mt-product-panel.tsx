"use client";

import * as React from "react";
import Link from "next/link";
import { FileText, History } from "lucide-react";
import Image from "next/image";
import { MtButton, Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { useProduct } from "@/lib/hooks/products/use-product";

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5 py-[2px] text-[11px]">
      <span className="w-14 shrink-0 text-right" style={{ color: MT.ink4 }}>
        {label}
      </span>
      <span
        className={/[0-9]/.test(value) ? "mt-mono font-semibold" : "font-medium"}
        style={{ color: MT.ink2 }}
      >
        {value || "—"}
      </span>
    </div>
  );
}

export function MtProductPanel({ sku }: { sku: string }) {
  const { data: product, isLoading } = useProduct(sku);

  const name =
    product?.translations?.es?.name ??
    product?.translations?.en?.name ??
    sku;

  const imageUrl = product?.primary_image_url ?? null;

  const qualityTone =
    product?.data_quality === "complete"
      ? ("success" as const)
      : product?.data_quality === "blocked"
        ? ("danger" as const)
        : ("warning" as const);

  const qualityLabel =
    product?.data_quality === "complete"
      ? "Calidad completa"
      : product?.data_quality === "blocked"
        ? "Bloqueado CG"
        : "Pendiente CG";

  if (isLoading) {
    return (
      <div
        className="flex w-[280px] shrink-0 flex-col gap-3 self-start rounded-lg border bg-mt-surface p-3.5"
        style={{ borderColor: MT.border }}
      >
        <div className="h-[160px] animate-pulse rounded-lg" style={{ background: MT.surface3 }} />
        <div className="h-4 w-3/5 animate-pulse rounded" style={{ background: MT.surface3 }} />
        <div className="h-20 animate-pulse rounded" style={{ background: MT.surface3 }} />
      </div>
    );
  }

  return (
    <div
      className="mt-card-lift flex w-[280px] shrink-0 flex-col self-start overflow-hidden rounded-lg border bg-mt-surface"
      style={{ borderColor: MT.border }}
    >
      {/* Foto MT */}
      <div
        className="relative flex h-[160px] w-full items-center justify-center border-b"
        style={{ background: MT.surface3, borderColor: MT.border }}
      >
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={name}
            fill
            className="object-contain p-3"
            sizes="280px"
          />
        ) : (
          <span className="mt-mono text-[10px] uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
            sin foto
          </span>
        )}
        <span
          className="absolute left-2 top-2 mt-mono rounded-[3px] border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.6px]"
          style={{ background: MT.brandSoft, borderColor: MT.brandBorder, color: MT.brand }}
        >
          MT
        </span>
      </div>

      <div className="flex flex-col gap-2.5 p-3.5">
        {/* SKU + nombre */}
        <div>
          <div className="mt-mono text-[11px] font-semibold" style={{ color: MT.ink }}>
            {sku}
          </div>
          <div className="mt-0.5 text-[12px] font-medium leading-[1.3]" style={{ color: MT.ink2 }}>
            {name}
          </div>
        </div>

        {/* Pills */}
        <div className="flex flex-wrap gap-1">
          {product?.series_detail?.tier_id && (
            <Pill tone="brand" mono>
              Tier {product.series_detail.tier_id.slice(0, 4)}
            </Pill>
          )}
          <Pill tone={qualityTone}>{qualityLabel}</Pill>
        </div>

        <div className="h-px w-full" style={{ background: MT.border }} />

        {/* Specs MT — campos directos del producto */}
        <div className="flex flex-col">
          <div
            className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.6px]"
            style={{ color: MT.ink4 }}
          >
            Ficha técnica
          </div>
          <SpecRow label="Material" value={product?.material ?? "—"} />
          <SpecRow label="Tipo" value={product?.type ?? "—"} />
          <SpecRow label="PN" value={product?.pn ?? "—"} />
          <SpecRow label="Conexión" value={product?.connection ?? "—"} />
          <SpecRow label="DN" value={product?.dn ?? "—"} />
        </div>

        <div className="h-px w-full" style={{ background: MT.border }} />

        {/* Links */}
        <div className="flex gap-1.5">
          <MtButton size="sm" className="flex-1 justify-center" asChild>
            <Link href={`/catalogo/${sku}`}>
              <FileText className="size-3.5" />
              Ficha
            </Link>
          </MtButton>
          <MtButton size="sm" className="flex-1 justify-center" asChild>
            <Link href={`/catalogo/${sku}/audit`}>
              <History className="size-3.5" />
              Histórico
            </Link>
          </MtButton>
        </div>
      </div>
    </div>
  );
}
