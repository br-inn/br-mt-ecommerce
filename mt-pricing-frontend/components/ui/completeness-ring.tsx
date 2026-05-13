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
  present: boolean;
}

function computeCompleteness(product: CompletenessRingProps["product"]): {
  percentage: number;
  missingFields: string[];
} {
  const nameEs = product.translations?.es?.name ?? null;
  const nameEn = product.translations?.en?.name ?? null;
  const nameAr = product.translations?.ar?.name ?? null;

  const checks: FieldCheck[] = [
    { key: "name_es",         label: "Nombre ES",           present: Boolean(nameEs) },
    { key: "brand",           label: "Marca",               present: Boolean(product.brand) },
    { key: "base_uom",        label: "UoM Base",            present: Boolean(product.base_uom) },
    { key: "gtin",            label: "GTIN",                present: Boolean(product.gtin) },
    { key: "lifecycle_status",label: "Estado ciclo de vida",present: Boolean(product.lifecycle_status) },
    { key: "name_en",         label: "Nombre EN",           present: Boolean(nameEn) },
    { key: "name_ar",         label: "Nombre AR",           present: Boolean(nameAr) },
    { key: "image",           label: "Imagen principal",    present: Boolean(product.primary_image_url) },
  ];

  const done = checks.filter((c) => c.present).length;
  const percentage = Math.round((done / checks.length) * 100);
  const missingFields = checks.filter((c) => !c.present).map((c) => c.label);

  return { percentage, missingFields };
}

export function CompletenessRing({
  product,
  size = 36,
}: CompletenessRingProps) {
  const { percentage, missingFields } = computeCompleteness(product);
  const [showTooltip, setShowTooltip] = useState(false);

  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (percentage / 100) * circumference;

  const color =
    percentage === 100
      ? "#22c55e"
      : percentage >= 75
        ? "#84cc16"
        : percentage >= 50
          ? "#eab308"
          : "#ef4444";

  const tooltipText =
    missingFields.length > 0
      ? `Faltan: ${missingFields.join(", ")}`
      : "Todos los campos completos.";

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        aria-label={`Completitud: ${percentage}%`}
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
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={3}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
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
            fill={color}
          >
            {percentage}%
          </text>
        </svg>
      </button>
      {showTooltip ? (
        <div className="absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-popover px-3 py-1.5 text-xs text-popover-foreground shadow-md ring-1 ring-border">
          <p className="font-semibold">Completitud: {percentage}%</p>
          {missingFields.length > 0 ? (
            <ul className="mt-1 space-y-0.5 text-muted-foreground">
              {missingFields.map((f) => (
                <li key={f}>· {f}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-0.5 text-green-600">{tooltipText}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
