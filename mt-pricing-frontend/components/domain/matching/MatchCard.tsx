"use client";

import * as React from "react";
import Image from "next/image";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import type { HumanQueueItem } from "@/lib/api/endpoints/human-queue";

// ---------------------------------------------------------------------------
// Confidence badge helpers
// ---------------------------------------------------------------------------
function confidenceVariant(value: number | null): "destructive" | "secondary" | "default" | "outline" {
  if (value === null) return "outline";
  if (value < 0.5) return "destructive";
  if (value < 0.75) return "secondary";
  return "default";
}

function confidenceLabel(value: number | null): string {
  if (value === null) return "N/A";
  return `${(value * 100).toFixed(0)}%`;
}

// ---------------------------------------------------------------------------
// Side card — muestra thumbnail + título de un candidato o producto MT
// ---------------------------------------------------------------------------
interface _SideCardProps {
  label: string;
  title: string;
  imageUrl?: string | null;
  subtitle?: string | null;
}

function _SideCard({ label, title, imageUrl, subtitle }: _SideCardProps) {
  return (
    <div className="flex flex-col items-center gap-2 min-w-0">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
      <div className="relative h-24 w-24 rounded-md border bg-muted overflow-hidden flex items-center justify-center">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={title}
            fill
            className="object-contain p-1"
            sizes="96px"
          />
        ) : (
          <span className="text-[10px] text-muted-foreground text-center px-1 leading-tight">
            Sin imagen
          </span>
        )}
      </div>
      <p
        className="text-xs text-center line-clamp-2 max-w-[120px] font-medium"
        title={title}
      >
        {title}
      </p>
      {subtitle && (
        <p className="text-[10px] text-muted-foreground text-center">{subtitle}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MatchCard
// ---------------------------------------------------------------------------
export interface MatchCardProps {
  item: HumanQueueItem;
  /** URL imagen del candidato externo (opcional — puede venir de specs_jsonb). */
  candidateImageUrl?: string | null;
  /** URL imagen del producto MT (opcional). */
  productImageUrl?: string | null;
  className?: string;
}

/**
 * MatchCard — muestra el par candidato + producto MT con:
 * - thumbnails de ambos lados
 * - confidence badge con color semántico
 * - SKU del producto MT y external_id del candidato
 *
 * Componente reutilizable para la cola de validación humana.
 */
export function MatchCard({
  item,
  candidateImageUrl,
  productImageUrl,
  className,
}: MatchCardProps) {
  const confidence =
    item.calibrated_confidence !== null && item.calibrated_confidence !== undefined
      ? parseFloat(item.calibrated_confidence)
      : null;

  const variant = confidenceVariant(confidence);

  return (
    <div
      className={cn(
        "flex items-center gap-4 rounded-lg border bg-card p-3 shadow-sm",
        className,
      )}
    >
      {/* Candidato externo */}
      <_SideCard
        label={item.channel.replace("_", " ")}
        title={item.title}
        imageUrl={candidateImageUrl ?? null}
        subtitle={item.brand ?? null}
      />

      {/* Centro: flecha + confidence */}
      <div className="flex flex-col items-center gap-1 shrink-0">
        <span className="text-muted-foreground text-lg">⇔</span>
        <Badge
          variant={variant}
          className={cn(
            "text-xs",
            variant === "destructive" && "bg-red-500 text-white border-transparent",
            variant === "secondary" &&
              "bg-yellow-400 text-yellow-900 border-transparent",
            variant === "default" && "bg-green-600 text-white border-transparent",
          )}
        >
          {confidenceLabel(confidence)}
        </Badge>
        {item.score !== undefined && (
          <span className="text-[10px] text-muted-foreground">
            score: {item.score}
          </span>
        )}
      </div>

      {/* Producto MT */}
      <_SideCard
        label="Producto MT"
        title={item.product_sku}
        imageUrl={productImageUrl ?? null}
      />
    </div>
  );
}
