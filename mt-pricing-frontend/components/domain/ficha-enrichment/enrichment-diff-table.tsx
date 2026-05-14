"use client";

import * as React from "react";

import { MtTd, MtTh } from "@/components/mt/primitives";
import { MtEmpty } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import type { FieldDiff } from "@/lib/api/endpoints/ficha-enrich";

// ---------------------------------------------------------------------------
// Field label map (Spanish)
// ---------------------------------------------------------------------------

const FIELD_LABELS: Record<string, string> = {
  family: "Familia",
  subfamily: "Subfamilia",
  type: "Tipo",
  material: "Material",
  dn: "DN",
  pn: "PN",
  connection: "Conexión",
  brand: "Marca",
  weight: "Peso",
  weight_unit: "Ud. peso",
  temp_min_c: "Temp. mín. (°C)",
  temp_max_c: "Temp. máx. (°C)",
  pressure_max_bar: "Presión máx. (bar)",
  size: "Talla",
  specs: "Specs técnicos",
  materials: "Materiales por componente",
  dimensions_by_dn: "Tabla de dimensiones",
  translations: "Traducciones",
  pt_curve_points: "Curva P/T",
  assets: "Planos y certificados",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") {
    const str = JSON.stringify(v);
    return str.length > 120 ? str.slice(0, 120) + "…" : str;
  }
  return String(v);
}

function fieldLabel(fieldName: string): string {
  return FIELD_LABELS[fieldName] ?? fieldName;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  diffs: FieldDiff[];
  selectedFields: Set<string>;
  onToggleField: (fieldName: string) => void;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Tabla de diferencias campo-a-campo entre el valor actual del producto
 * y el valor extraído del PDF. Permite seleccionar individualmente los
 * campos que se quieren aplicar.
 *
 * UX:
 *  - Filas con cambios (has_change=true): checkboxes + valor actual + valor
 *    extraído. Hacer clic en la fila alterna el checkbox.
 *  - Campos sin cambio: sección colapsada <details>.
 *  - Estado vacío si no hay diffs.
 */
export function EnrichmentDiffTable({
  diffs,
  selectedFields,
  onToggleField,
}: Props) {
  const changedDiffs = diffs.filter((d) => d.has_change);
  const unchangedDiffs = diffs.filter((d) => !d.has_change);

  if (diffs.length === 0) {
    return (
      <MtEmpty
        title="Sin diferencias"
        hint="No se detectaron campos distintos entre el PDF y el producto actual."
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* ------------------------------------------------------------------ */}
      {/* Changed fields table                                                */}
      {/* ------------------------------------------------------------------ */}
      {changedDiffs.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border" style={{ borderColor: MT.border }}>
          <table className="w-full border-separate border-spacing-0">
            <thead>
              <tr>
                <MtTh scope="col" style={{ width: "2.5rem" }}>{/* checkbox col */}</MtTh>
                <MtTh scope="col">Campo</MtTh>
                <MtTh scope="col">
                  <span style={{ color: MT.ink3 }}>Valor actual</span>
                </MtTh>
                <MtTh scope="col">
                  <span style={{ color: MT.brand }}>Valor extraído</span>
                </MtTh>
              </tr>
            </thead>
            <tbody>
              {changedDiffs.map((diff) => (
                <DiffRow
                  key={diff.field_name}
                  diff={diff}
                  checked={selectedFields.has(diff.field_name)}
                  onToggle={() => onToggleField(diff.field_name)}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {/* ------------------------------------------------------------------ */}
      {/* Unchanged fields — collapsed                                         */}
      {/* ------------------------------------------------------------------ */}
      {unchangedDiffs.length > 0 ? (
        <details>
          <summary
            className="mt-mono cursor-pointer select-none text-[10.5px] uppercase tracking-[0.5px]"
            style={{ color: MT.ink3 }}
          >
            Sin cambios ({unchangedDiffs.length} campos coinciden)
          </summary>
          <div className="mt-2 overflow-x-auto rounded-lg border" style={{ borderColor: MT.border }}>
            <table className="w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <MtTh scope="col">Campo</MtTh>
                  <MtTh scope="col">Valor actual</MtTh>
                </tr>
              </thead>
              <tbody>
                {unchangedDiffs.map((diff) => (
                  <tr key={diff.field_name}>
                    <MtTd mono>{fieldLabel(diff.field_name)}</MtTd>
                    <MtTd>
                      <span style={{ color: MT.ink3 }}>
                        {formatValue(diff.current_value)}
                      </span>
                    </MtTd>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: single changed-field row
// ---------------------------------------------------------------------------

interface DiffRowProps {
  diff: FieldDiff;
  checked: boolean;
  onToggle: () => void;
}

function DiffRow({ diff, checked, onToggle }: DiffRowProps) {
  return (
    <tr
      role="button"
      tabIndex={0}
      aria-label={`Toggle ${FIELD_LABELS[diff.field_name] ?? diff.field_name}`}
      className="cursor-pointer transition-colors"
      style={{
        backgroundColor: checked ? `${MT.brand}0d` : undefined,
      }}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle();
        }
      }}
    >
      {/* Checkbox */}
      <MtTd>
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          className="cursor-pointer"
          aria-label={`Seleccionar campo ${fieldLabel(diff.field_name)}`}
        />
      </MtTd>

      {/* Field name */}
      <MtTd mono>
        <span style={{ color: MT.ink }}>{fieldLabel(diff.field_name)}</span>
        {diff.validation_error ? (
          <span
            className="ml-2 text-[10.5px] italic"
            style={{ color: MT.danger }}
          >
            {diff.validation_error}
          </span>
        ) : null}
      </MtTd>

      {/* Current value */}
      <MtTd>
        <span style={{ color: MT.ink3 }}>{formatValue(diff.current_value)}</span>
      </MtTd>

      {/* Extracted value */}
      <MtTd>
        <span style={{ color: MT.brand }}>{formatValue(diff.extracted_value)}</span>
      </MtTd>
    </tr>
  );
}
