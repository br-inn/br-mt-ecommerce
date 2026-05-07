"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils/cn";
import type { Language, TranslationStatus } from "@/lib/api/endpoints/products";

const STYLES: Record<TranslationStatus | "missing", string> = {
  draft: "bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100",
  pending: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-100",
  approved: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
  missing: "bg-muted text-muted-foreground",
};

interface Props {
  language: Language | "en";
  status: TranslationStatus | null | undefined;
  className?: string;
}

/**
 * Pill para mostrar el estado de traducción por idioma.
 * Cuando `status` es null/undefined, marcamos "missing".
 */
export function TranslationStatusPill({ language, status, className }: Props) {
  const t = useTranslations("catalog.translations");
  const key: keyof typeof STYLES = status ?? "missing";
  const label = t(`status.${key}`);
  const langLabel = language === "en" ? "EN" : language === "es" ? "ES" : "AR";
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 border-transparent text-xs font-medium", STYLES[key], className)}
      aria-label={`${langLabel} ${label}`}
      dir="ltr"
    >
      <span className="font-semibold">{langLabel}</span>
      <span aria-hidden>·</span>
      <span>{label}</span>
    </Badge>
  );
}
