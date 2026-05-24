"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight, ImageIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import { Pill } from "@/components/mt/primitives";
import { useProduct } from "@/lib/hooks/products/use-product";
import { getProductName } from "@/lib/utils/product-display";

function KVP({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={`truncate text-sm font-semibold ${mono ? "font-mono" : ""}`}>{value ?? "—"}</dd>
    </div>
  );
}

interface Props {
  sku: string;
}

export function AmazonHeader({ sku }: Props) {
  const { data: product, isLoading, isError } = useProduct(sku);

  const [navSkus, setNavSkus] = useState<string[]>([]);
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("mt-amazon-nav");
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw) setNavSkus(JSON.parse(raw) as string[]);
    } catch {
      // ignore
    }
  }, []);

  const navIdx = navSkus.indexOf(sku);
  const prevSku = navIdx > 0 ? navSkus[navIdx - 1] : null;
  const nextSku = navIdx >= 0 && navIdx < navSkus.length - 1 ? navSkus[navIdx + 1] : null;
  const showNav = navSkus.length > 0 && navIdx >= 0;

  if (isLoading) {
    return (
      <div className="flex gap-4">
        <Skeleton className="h-[140px] w-[140px] shrink-0 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        No se encontró el producto.
      </div>
    );
  }

  return (
    <>
      {showNav ? (
        <div className="mb-2 flex items-center gap-3 text-[11.5px] text-muted-foreground">
          <Link href="/canales/marketplace/amazon" className="transition-colors hover:text-foreground">
            ← Amazon UAE
          </Link>
          <span className="opacity-20">|</span>
          {prevSku ? (
            <Link
              href={`/canales/marketplace/amazon/${prevSku}`}
              className="flex items-center gap-0.5 font-mono transition-colors hover:text-foreground"
            >
              <ChevronLeft className="size-3.5" />
              {prevSku}
            </Link>
          ) : (
            <span className="flex items-center gap-0.5 opacity-30">
              <ChevronLeft className="size-3.5" />—
            </span>
          )}
          <span className="tabular-nums">
            {navIdx + 1} / {navSkus.length}
          </span>
          {nextSku ? (
            <Link
              href={`/canales/marketplace/amazon/${nextSku}`}
              className="flex items-center gap-0.5 font-mono transition-colors hover:text-foreground"
            >
              {nextSku}
              <ChevronRight className="size-3.5" />
            </Link>
          ) : (
            <span className="flex items-center gap-0.5 opacity-30">
              —<ChevronRight className="size-3.5" />
            </span>
          )}
        </div>
      ) : null}

      <div className="flex gap-5">
        <div className="shrink-0">
          {product.primary_image_url ? (
            <img
              src={product.primary_image_url}
              alt={getProductName(product)}
              className="h-[140px] w-[140px] rounded-lg object-cover"
              style={{ border: "1px solid hsl(var(--border))" }}
            />
          ) : (
            <div
              className="flex h-[140px] w-[140px] items-center justify-center rounded-lg"
              style={{ border: "1px solid hsl(var(--border))", background: "hsl(var(--muted)/0.4)" }}
            >
              <ImageIcon className="h-10 w-10 text-muted-foreground/25" strokeWidth={1.2} />
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{product.sku}</span>
              <Pill tone="brand">Amazon UAE</Pill>
              <LifecycleStatusBadge status={product.lifecycle_status} />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">{getProductName(product)}</h1>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border bg-muted/30 p-3 sm:grid-cols-4">
            <KVP label="GTIN" value={product.gtin} mono />
            <KVP label="DN" value={product.dn} />
            <KVP label="PN" value={product.pn} />
            <KVP label="Peso" value={product.weight_kg ? `${product.weight_kg} kg` : null} />
          </dl>
        </div>
      </div>
    </>
  );
}
