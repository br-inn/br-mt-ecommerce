// mt-pricing-frontend/app/(app)/imports/_components/mapping-step.tsx
"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { AlertCircle } from "lucide-react";
import {
  type AnalyzeImportResponse,
  type ColumnMappingItem,
} from "@/lib/api/endpoints/imports";
import { cn } from "@/lib/utils/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

// Campos target disponibles (ordenados por frecuencia de uso).
const TARGET_FIELDS = [
  { value: "_skip", label: "— Ignorar columna —" },
  { value: "sku", label: "sku (clave primaria)" },
  { value: "family", label: "family" },
  { value: "erp_name", label: "erp_name" },
  { value: "hs_code", label: "hs_code" },
  { value: "intrastat_code", label: "intrastat_code" },
  { value: "connection", label: "connection" },
  { value: "brand", label: "brand" },
  { value: "weight", label: "weight (kg)" },
  { value: "bore_mm", label: "bore_mm" },
  { value: "pressure_max_bar", label: "pressure_max_bar" },
  { value: "temp_min_c", label: "temp_min_c" },
  { value: "temp_max_c", label: "temp_max_c" },
  { value: "dimensions.high_mm", label: "dimensions.high_mm" },
  { value: "dimensions.wide_mm", label: "dimensions.wide_mm" },
  { value: "dimensions.deep_mm", label: "dimensions.deep_mm" },
  { value: "packaging.qty_per_box", label: "packaging.qty_per_box" },
  { value: "packaging.box_high_mm", label: "packaging.box_high_mm" },
  { value: "packaging.box_wide_mm", label: "packaging.box_wide_mm" },
  { value: "packaging.box_deep_mm", label: "packaging.box_deep_mm" },
  { value: "packaging.moq_inner_box", label: "packaging.moq_inner_box" },
  { value: "packaging.x_pallet", label: "packaging.x_pallet" },
  { value: "specs.ean_individual", label: "specs.ean_individual" },
  { value: "specs.ean_box", label: "specs.ean_box" },
  { value: "specs.ean_inner_box", label: "specs.ean_inner_box" },
  { value: "specs.name_en", label: "specs.name_en" },
  { value: "specs.name_es", label: "specs.name_es" },
  { value: "specs.name_fr", label: "specs.name_fr" },
  { value: "specs.name_de", label: "specs.name_de" },
  { value: "specs.image_url", label: "specs.image_url" },
  { value: "specs.standards", label: "specs.standards" },
  { value: "specs.certifications", label: "specs.certifications" },
  { value: "specs.series_tags", label: "specs.series_tags" },
  { value: "specs.material_category", label: "specs.material_category" },
  { value: "specs.family_type", label: "specs.family_type" },
  { value: "specs.en_pim", label: "specs.en_pim" },
  { value: "specs.en_catalogo", label: "specs.en_catalogo" },
  { value: "specs.completitud_pct", label: "specs.completitud_pct" },
  { value: "specs.salidas", label: "specs.salidas" },
  { value: "specs.catalog_page", label: "specs.catalog_page" },
];

const TRANSFORMS = [
  { value: "text", label: "text" },
  { value: "int", label: "int" },
  { value: "decimal", label: "decimal" },
  { value: "cm_to_mm", label: "cm → mm (×10)" },
  { value: "ean", label: "ean (barcode)" },
  { value: "bool_check", label: "bool (✓/yes)" },
  { value: "percent", label: "percent (0–100)" },
];

interface Props {
  analysis: AnalyzeImportResponse;
  onBack: () => void;
  onConfirm: (mapping: ColumnMappingItem[]) => void;
  isLoading?: boolean;
}

export function MappingStep({ analysis, onBack, onConfirm, isLoading }: Props) {
  const t = useTranslations("imports.mapping");
  const [mapping, setMapping] = React.useState<ColumnMappingItem[]>(
    () => [...analysis.proposed_mapping],
  );

  const updateItem = (idx: number, patch: Partial<ColumnMappingItem>) => {
    setMapping((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, ...patch } : item)),
    );
  };

  const skuMapped = mapping.some((m) => m.target_field === "sku");

  const firstSampleRow = analysis.sample_rows[0] ?? [];
  const headerIndex: Record<string, number> = {};
  analysis.headers.forEach((h, i) => {
    headerIndex[h] = i;
  });

  return (
    <div className="space-y-4" data-testid="mapping-step">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            {t("subtitle", { cols: analysis.headers.length, row: analysis.detected_header_row + 1 })}
          </p>
        </div>
        {!skuMapped && (
          <div className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            {t("skuRequired")}
          </div>
        )}
      </div>

      <div className="rounded-md border overflow-auto max-h-[60vh]">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-muted/80 backdrop-blur">
            <tr>
              <th className="px-3 py-2 text-left font-medium">{t("colExcel")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colSample")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colTarget")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colTransform")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("colConfidence")}</th>
            </tr>
          </thead>
          <tbody>
            {mapping.map((item, idx) => {
              const colIdx = headerIndex[item.excel_col];
              const sampleVal = colIdx !== undefined ? firstSampleRow[colIdx] : undefined;
              const isSkip = item.target_field === "_skip";
              return (
                <tr
                  key={item.excel_col}
                  className={cn(
                    "border-t transition-colors",
                    isSkip ? "opacity-50" : "hover:bg-muted/30",
                  )}
                >
                  <td className="px-3 py-1.5 font-mono">{item.excel_col}</td>
                  <td className="px-3 py-1.5 text-muted-foreground max-w-[120px] truncate">
                    {sampleVal ?? "—"}
                  </td>
                  <td className="px-3 py-1.5 min-w-[200px]">
                    <Select
                      value={item.target_field}
                      onValueChange={(v) => updateItem(idx, { target_field: v })}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TARGET_FIELDS.map((f) => (
                          <SelectItem key={f.value} value={f.value} className="text-xs">
                            {f.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-1.5 min-w-[140px]">
                    <Select
                      value={item.transform}
                      onValueChange={(v) => updateItem(idx, { transform: v })}
                      disabled={isSkip}
                    >
                      <SelectTrigger className="h-7 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TRANSFORMS.map((tr) => (
                          <SelectItem key={tr.value} value={tr.value} className="text-xs">
                            {tr.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge
                      variant={item.confidence >= 0.85 ? "default" : "secondary"}
                      className="text-[10px]"
                    >
                      {Math.round(item.confidence * 100)}%
                    </Badge>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack} disabled={isLoading}>
          {t("back")}
        </Button>
        <Button
          onClick={() => onConfirm(mapping)}
          disabled={!skuMapped || isLoading}
        >
          {isLoading ? t("loading") : t("confirm")}
        </Button>
      </div>
    </div>
  );
}
