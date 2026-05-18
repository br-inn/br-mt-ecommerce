"use client";

import Link from "next/link";
import { Pencil } from "lucide-react";
import { MT } from "@/components/mt/tokens";
import { QualityBadge, Thumb } from "@/components/mt/primitives";
import { LifecycleStatusBadge } from "@/components/ui/lifecycle-status-badge";
import type { ProductListItem } from "@/lib/api/endpoints/products";
import { getProductName } from "@/lib/utils/product-display";

interface ProductGridCardProps {
  item: ProductListItem;
  onQuickEdit: (sku: string) => void;
  onNavClick: () => void;
}

export function ProductGridCard({ item, onQuickEdit, onNavClick }: ProductGridCardProps) {
  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-lg border transition-shadow hover:shadow-md"
      style={{ borderColor: MT.border, background: MT.surface }}
    >
      {/* Imagen — link al detalle */}
      <Link
        href={`/catalogo/${item.sku}`}
        onClick={onNavClick}
        className="block"
      >
        <div
          className="flex h-[120px] items-center justify-center overflow-hidden"
          style={{ background: MT.surface2 }}
        >
          {item.primary_image_url ? (
            <img
              src={item.primary_image_url}
              alt=""
              loading="lazy"
              decoding="async"
              className="h-full w-full object-cover"
            />
          ) : (
            <Thumb />
          )}
        </div>
      </Link>

      {/* Info */}
      <div className="flex flex-1 flex-col gap-1 p-2.5">
        <span
          className="mt-mono text-[10px] uppercase tracking-wider"
          style={{ color: MT.brand }}
        >
          {item.sku}
        </span>
        <Link
          href={`/catalogo/${item.sku}`}
          onClick={onNavClick}
          className="line-clamp-2 text-[12px] font-medium leading-tight hover:underline"
          style={{ color: MT.ink }}
        >
          {getProductName(item)}
        </Link>
        {item.family ? (
          <span
            className="mt-mono truncate text-[10.5px]"
            style={{ color: MT.ink4 }}
          >
            {item.family}
          </span>
        ) : null}

        {/* Footer: badges + acción */}
        <div className="mt-auto flex items-center justify-between pt-1">
          <div className="flex items-center gap-1">
            <QualityBadge v={item.data_quality} />
            <LifecycleStatusBadge status={item.lifecycle_status} />
          </div>
          <button
            type="button"
            onClick={() => onQuickEdit(item.sku)}
            className="rounded p-1 opacity-0 transition-opacity group-hover:opacity-100"
            style={{ color: MT.ink3 }}
            title="Editar rápido"
          >
            <Pencil className="size-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
