"use client";

import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import type { DataQuality } from "@/lib/api/endpoints/products";

const STYLES: Record<DataQuality, { className: string; Icon: typeof CheckCircle2; label: string }> = {
  complete: {
    className:
      "bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-100",
    Icon: CheckCircle2,
    label: "Complete",
  },
  partial: {
    className:
      "bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-900/40 dark:text-amber-100",
    Icon: AlertTriangle,
    label: "Partial",
  },
  blocked: {
    className:
      "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-900/40 dark:text-rose-100",
    Icon: XCircle,
    label: "Blocked",
  },
};

interface Props {
  value: DataQuality;
  className?: string;
}

/**
 * Badge semántico para `data_quality` de un Product.
 * Color + icono para no depender solo de color (A11y).
 */
export function DataQualityBadge({ value, className }: Props) {
  const { className: styleClass, Icon, label } = STYLES[value];
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 border", styleClass, className)}
      data-testid={`data-quality-${value}`}
      aria-label={label}
    >
      <Icon className="h-3 w-3" aria-hidden />
      <span>{label}</span>
    </Badge>
  );
}
