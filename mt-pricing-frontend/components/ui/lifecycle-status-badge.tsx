"use client";

import { Badge } from "@/components/ui/badge";
import type { ProductLifecycleStatus } from "@/lib/api/endpoints/products";

const LIFECYCLE_CONFIG: Record<
  ProductLifecycleStatus,
  { label: string; dotClass: string; badgeVariant: "default" | "secondary" | "destructive" | "outline" }
> = {
  draft:        { label: "Borrador",      dotClass: "bg-gray-400",    badgeVariant: "secondary"   },
  in_review:    { label: "En Revisión",   dotClass: "bg-yellow-500",  badgeVariant: "outline"     },
  active:       { label: "Activo",        dotClass: "bg-green-500",   badgeVariant: "default"     },
  deprecated:   { label: "Obsoleto",      dotClass: "bg-orange-500",  badgeVariant: "outline"     },
  replaced:     { label: "Reemplazado",   dotClass: "bg-orange-400",  badgeVariant: "outline"     },
  discontinued: { label: "Discontinuado", dotClass: "bg-red-500",     badgeVariant: "destructive" },
};

interface Props {
  status: ProductLifecycleStatus | null | undefined;
  className?: string;
}

export function LifecycleStatusBadge({ status, className }: Props) {
  if (!status) return null;
  const cfg = LIFECYCLE_CONFIG[status] ?? LIFECYCLE_CONFIG.active;
  return (
    <Badge variant={cfg.badgeVariant} className={`gap-1.5 ${className ?? ""}`}>
      <span className={`inline-block h-2 w-2 rounded-full ${cfg.dotClass}`} />
      {cfg.label}
    </Badge>
  );
}
