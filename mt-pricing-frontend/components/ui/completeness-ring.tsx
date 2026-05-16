"use client";

import { useState } from "react";
import type { Product } from "@/lib/api/endpoints/products";

interface CompletenessRingProps {
  product: Pick<
    Product,
    | "lifecycle_status"
    | "brand"
    | "base_uom"
    | "gtin"
    | "translations"
    | "primary_image_url"
  >;
  size?: number;
}

interface FieldCheck {
  key: string;
  label: string;
  group: "basic" | "translations" | "image" | "specs";
  present: boolean;
}

interface GroupResult {
  label: string;
  missing: string[];
}

// Group labels for Akeneo-style tooltip (UX-06)
const GROUP_LABELS: Record<FieldCheck["group"], string> = {
  basic:        "Datos básicos",
  translations: "Traducciones",
  image:        "Imagen",
  specs:        "Especificaciones",
};

function computeCompleteness(product: CompletenessRingProps["product"]): {
  percentage: number;
  groups: GroupResult[];
} {
  const nameEs = product.translations?.es?.name ?? null;
  const nameEn = product.translations?.en?.name ?? null;
  const nameAr = product.translations?.ar?.name ?? null;

  const checks: FieldCheck[] = [
    { key: "name_es",          label: "Nombre ES",            group: "basic",        present: Boolean(nameEs) },
    { key: "brand",            label: "Marca",                group: "basic",        present: Boolean(product.brand) },
    { key: "base_uom",         label: "UoM Base",             group: "specs",        present: Boolean(product.base_uom) },
    { key: "gtin",             label: "GTIN",                 group: "specs",        present: Boolean(product.gtin) },
    { key: "lifecycle_status", label: "Estado ciclo de vida", group: "basic",        present: Boolean(product.lifecycle_status) },
    { key: "name_en",          label: "Nombre EN",            group: "translations", present: Boolean(nameEn) },
    { key: "name_ar",          label: "Nombre AR",            group: "translations", present: Boolean(nameAr) },
    { key: "image",            label: "Imagen principal",     group: "image",        present: Boolean(product.primary_image_url) },
  ];

  const done = checks.filter((c) => c.present).length;
  const percentage = Math.round((done / checks.length) * 100);

  // Build per-group missing lists
  const groupMap = new Map<FieldCheck["group"], string[]>();
  for (const check of checks) {
    if (!check.present) {
      const arr = groupMap.get(check.group) ?? [];
      arr.push(check.label);
      groupMap.set(check.group, arr);
    }
  }

  const groups: GroupResult[] = (
    ["basic", "translations", "image", "specs"] as const
  )
    .filter((g) => (groupMap.get(g)?.length ?? 0) > 0)
    .map((g) => ({ label: GROUP_LABELS[g], missing: groupMap.get(g)! }));

  return { percentage, groups };
}

// CSS-var-driven color classes (Tailwind v4 design tokens)
function getRingColor(percentage: number): string {
  if (percentage === 100) return "text-green-500";
  if (percentage >= 75)   return "text-lime-500";
  if (percentage >= 50)   return "text-yellow-500";
  return "text-red-500";
}

function getRingStroke(percentage: number): string {
  if (percentage === 100) return "stroke-green-500";
  if (percentage >= 75)   return "stroke-lime-500";
  if (percentage >= 50)   return "stroke-yellow-500";
  return "stroke-red-500";
}

export function CompletenessRing({
  product,
  size = 36,
}: CompletenessRingProps) {
  const { percentage, groups } = computeCompleteness(product);
  const [showTooltip, setShowTooltip] = useState(false);

  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (percentage / 100) * circumference;

  const ringColor  = getRingColor(percentage);
  const ringStroke = getRingStroke(percentage);

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={`Completitud del perfil: ${percentage}%`}
        className="flex items-center gap-1 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
      >
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-hidden
          className="shrink-0"
        >
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            className="stroke-muted-foreground/20"
            strokeWidth={3}
          />
          {/* Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            className={ringStroke}
            strokeWidth={3}
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
          <text
            x={size / 2}
            y={size / 2 + 4}
            textAnchor="middle"
            fontSize="9"
            fontWeight="600"
            className={ringColor}
          >
            {percentage}%
          </text>
        </svg>
      </button>

      {showTooltip ? (
        <div
          className="absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 min-w-[180px] rounded-md bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md ring-1 ring-border"
          role="tooltip"
        >
          <p className="font-semibold">Completitud: {percentage}%</p>
          {groups.length > 0 ? (
            <ul className="mt-1.5 space-y-1">
              {groups.map((g) => (
                <li key={g.label}>
                  <span className="font-medium text-foreground">{g.label}:</span>{" "}
                  <span className="text-muted-foreground">{g.missing.join(", ")}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-green-600">Todos los campos completos.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
