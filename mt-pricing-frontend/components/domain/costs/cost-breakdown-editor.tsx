"use client";

/**
 * CostBreakdownEditor — editor de componentes JSONB para US-1A-04-04 AC#2.
 *
 * - Recibe el `breakdown` actual y un template (required + optional fields)
 *   inferido del scheme. El frontend NO consulta el template aquí — el caller
 *   pasa los keys (lo lee de un endpoint/seed local en futuro sprint).
 * - Convención de claves: `*_aed`, `*_eur` (o currency_origin lower), `*_pct`.
 *   El editor renderiza un input numérico por clave conocida + un botón
 *   "Añadir componente" para keys ad-hoc (que generarán un warning en backend).
 * - Errores 422 inline por componente — se reciben vía `errors` prop.
 *
 * Estilo: primitivos `components/mt`. Sin shadcn aquí.
 */

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import { MtButton, MtTd, MtTh } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import type { CostBreakdown } from "@/lib/api/endpoints/costs";

export interface CostBreakdownEditorProps {
  breakdown: CostBreakdown;
  required?: string[];
  optional?: string[];
  /** Errores inline por field key (mapa field → mensaje). */
  errors?: Record<string, string>;
  onChange: (next: CostBreakdown) => void;
  disabled?: boolean;
}

export function CostBreakdownEditor({
  breakdown,
  required = [],
  optional = [],
  errors = {},
  onChange,
  disabled = false,
}: CostBreakdownEditorProps) {
  // Las keys que se renderizan = required ∪ optional ∪ keys actuales del breakdown.
  // Garantiza que campos extras escritos por el importer permanezcan visibles.
  const declaredKeys = React.useMemo(
    () => Array.from(new Set([...required, ...optional])),
    [required, optional],
  );
  const adhocKeys = React.useMemo(
    () => Object.keys(breakdown).filter((k) => !declaredKeys.includes(k)),
    [breakdown, declaredKeys],
  );

  const [newKey, setNewKey] = React.useState("");

  const setField = (key: string, raw: string) => {
    if (disabled) return;
    const next: CostBreakdown = { ...breakdown };
    if (raw === "" || raw === null || raw === undefined) {
      delete next[key];
    } else {
      const parsed = Number(raw);
      next[key] = Number.isFinite(parsed) ? parsed : raw;
    }
    onChange(next);
  };

  const removeField = (key: string) => {
    if (disabled) return;
    const next: CostBreakdown = { ...breakdown };
    delete next[key];
    onChange(next);
  };

  const addAdhocField = () => {
    if (disabled) return;
    const key = newKey.trim();
    if (!key) return;
    if (Object.prototype.hasOwnProperty.call(breakdown, key)) {
      setNewKey("");
      return;
    }
    onChange({ ...breakdown, [key]: 0 });
    setNewKey("");
  };

  const renderRow = (key: string, isRequired: boolean, isAdhoc: boolean) => {
    const value = breakdown[key];
    const stringValue =
      value === null || value === undefined ? "" : String(value);
    const error = errors[key];
    return (
      <tr key={key}>
        <MtTd mono className="w-[40%]">
          <span style={{ color: MT.ink2 }}>{key}</span>
          {isRequired ? (
            <span
              className="ml-1 text-[10px] uppercase tracking-wide"
              style={{ color: MT.danger }}
              aria-label="required"
            >
              *
            </span>
          ) : null}
          {isAdhoc ? (
            <span
              className="ml-1 text-[10px] uppercase tracking-wide"
              style={{ color: MT.warning }}
            >
              ad-hoc
            </span>
          ) : null}
        </MtTd>
        <MtTd className="w-[40%]">
          <input
            type="number"
            inputMode="decimal"
            step="0.0001"
            min={0}
            value={stringValue}
            onChange={(e) => setField(key, e.target.value)}
            disabled={disabled}
            data-testid={`breakdown-input-${key}`}
            aria-invalid={!!error}
            className="w-full rounded-[4px] border px-2 py-1 text-[12.5px] mt-tnum"
            style={{
              borderColor: error ? MT.danger : MT.border,
              backgroundColor: disabled ? MT.surface3 : MT.surface,
              color: MT.ink,
            }}
          />
          {error ? (
            <p
              className="mt-1 text-[11px]"
              style={{ color: MT.danger }}
              data-testid={`breakdown-error-${key}`}
            >
              {error}
            </p>
          ) : null}
        </MtTd>
        <MtTd className="w-[20%] text-right">
          {isAdhoc ? (
            <MtButton
              size="sm"
              tone="danger"
              icon={<Trash2 className="size-3" />}
              onClick={() => removeField(key)}
              disabled={disabled}
              aria-label={`remove-${key}`}
            >
              Quitar
            </MtButton>
          ) : null}
        </MtTd>
      </tr>
    );
  };

  return (
    <div className="flex flex-col gap-3" data-testid="cost-breakdown-editor">
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <MtTh>Componente</MtTh>
            <MtTh>Valor</MtTh>
            <MtTh className="text-right">Acción</MtTh>
          </tr>
        </thead>
        <tbody>
          {required.map((k) => renderRow(k, true, false))}
          {optional.map((k) => renderRow(k, false, false))}
          {adhocKeys.map((k) => renderRow(k, false, true))}
        </tbody>
      </table>

      {!disabled ? (
        <div
          className="flex items-center gap-2 rounded-md border p-2"
          style={{ borderColor: MT.border, backgroundColor: MT.surface2 }}
        >
          <input
            type="text"
            placeholder="otro_componente_aed"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addAdhocField();
              }
            }}
            data-testid="breakdown-new-key"
            className="flex-1 rounded-[4px] border px-2 py-1 text-[12.5px]"
            style={{ borderColor: MT.border, backgroundColor: MT.surface }}
          />
          <MtButton
            size="sm"
            tone="primary"
            icon={<Plus className="size-3" />}
            onClick={addAdhocField}
            disabled={!newKey.trim()}
            data-testid="breakdown-add"
          >
            Añadir componente
          </MtButton>
        </div>
      ) : null}

      <p className="text-[11px]" style={{ color: MT.ink3 }}>
        Convención de sufijos: <strong>_aed</strong> (importes en AED),{" "}
        <strong>_eur</strong> (importes en EUR — convertirá vía FX),{" "}
        <strong>_pct</strong> (porcentaje sobre el subtotal).
      </p>
    </div>
  );
}

export default CostBreakdownEditor;
