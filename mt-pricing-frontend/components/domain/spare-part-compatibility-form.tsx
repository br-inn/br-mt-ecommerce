"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils/cn";
import type {
  CompatibilityKind,
  CompatibilityOwnerType,
  ProductCompatibilityCreate,
} from "@/lib/api/endpoints/products";

interface Props {
  /** SKU origen (producto al que se vinculan los recambios). */
  sku: string;
  /** Callback de submit — recibe el payload listo para `productsApi.addCompatibility`. */
  onSubmit: (payload: ProductCompatibilityCreate) => Promise<void> | void;
  /** Estado de "saving" para deshabilitar inputs durante la mutation. */
  isSaving?: boolean;
  /** Error a renderizar bajo el form (ya formateado). */
  errorMessage?: string | null;
  className?: string;
  /** Valores iniciales — útil para tests / edición. */
  initialValues?: Partial<ProductCompatibilityCreate>;
}

const KIND_OPTIONS: { value: CompatibilityKind; label: string }[] = [
  { value: "spare_part", label: "Recambio" },
  { value: "accessory", label: "Accesorio" },
  { value: "replaces", label: "Reemplaza a" },
  { value: "replaced_by", label: "Reemplazado por" },
  { value: "compatible_with", label: "Compatible con" },
];

const OWNER_OPTIONS: { value: CompatibilityOwnerType; label: string }[] = [
  { value: "product", label: "Producto" },
  { value: "variant", label: "Variante" },
  { value: "series", label: "Serie" },
];

/**
 * Formulario para crear un enlace de compatibilidad (Wave 7 + Fase 5).
 *
 * Fase 5 — añade:
 *  - Radio `owner_type` (default 'product').
 *  - Inputs `dn_min` / `dn_max` visibles SOLO cuando owner_type='series'.
 *
 * El componente no conoce nada de TanStack — el llamante envuelve el submit
 * con su `useMutation` y le pasa `isSaving` + `errorMessage`.
 */
export function SparePartCompatibilityForm({
  sku,
  onSubmit,
  isSaving = false,
  errorMessage = null,
  className,
  initialValues,
}: Props) {
  const [compatibleSku, setCompatibleSku] = React.useState(
    initialValues?.compatible_with_sku ?? "",
  );
  const [kind, setKind] = React.useState<CompatibilityKind>(
    initialValues?.kind ?? "spare_part",
  );
  const [ownerType, setOwnerType] = React.useState<CompatibilityOwnerType>(
    initialValues?.owner_type ?? "product",
  );
  const [dnMin, setDnMin] = React.useState<string>(
    initialValues?.dn_min != null ? String(initialValues.dn_min) : "",
  );
  const [dnMax, setDnMax] = React.useState<string>(
    initialValues?.dn_max != null ? String(initialValues.dn_max) : "",
  );
  const [notes, setNotes] = React.useState<string>(initialValues?.notes ?? "");
  const [localError, setLocalError] = React.useState<string | null>(null);

  const showDnRange = ownerType === "series";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);

    const trimmedSku = compatibleSku.trim();
    if (!trimmedSku) {
      setLocalError("El SKU compatible es obligatorio.");
      return;
    }
    if (trimmedSku === sku) {
      setLocalError("No se puede enlazar un producto consigo mismo.");
      return;
    }

    const dnMinN = dnMin === "" ? null : Number(dnMin);
    const dnMaxN = dnMax === "" ? null : Number(dnMax);
    if (dnMinN !== null && Number.isNaN(dnMinN)) {
      setLocalError("dn_min debe ser un número.");
      return;
    }
    if (dnMaxN !== null && Number.isNaN(dnMaxN)) {
      setLocalError("dn_max debe ser un número.");
      return;
    }
    if (dnMinN !== null && dnMaxN !== null && dnMaxN < dnMinN) {
      setLocalError("dn_max debe ser >= dn_min.");
      return;
    }

    const payload: ProductCompatibilityCreate = {
      compatible_with_sku: trimmedSku,
      kind,
      owner_type: ownerType,
      notes: notes.trim() ? notes.trim() : null,
    };
    if (showDnRange) {
      payload.dn_min = dnMinN;
      payload.dn_max = dnMaxN;
    }

    await onSubmit(payload);
  };

  const displayError = localError ?? errorMessage;

  return (
    <form
      onSubmit={handleSubmit}
      className={cn("space-y-4", className)}
      aria-label="Formulario de compatibilidad"
    >
      <div className="space-y-1.5">
        <Label htmlFor="compat-sku">SKU compatible</Label>
        <Input
          id="compat-sku"
          name="compatible_with_sku"
          value={compatibleSku}
          onChange={(e) => setCompatibleSku(e.target.value)}
          disabled={isSaving}
          placeholder="SKU-123"
          autoComplete="off"
          required
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="compat-kind">Tipo de relación</Label>
        <Select
          value={kind}
          onValueChange={(v) => setKind(v as CompatibilityKind)}
          disabled={isSaving}
        >
          <SelectTrigger id="compat-kind" aria-label="Tipo de relación">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {KIND_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <fieldset className="space-y-1.5">
        <legend className="text-sm font-medium">Tipo de owner</legend>
        <div className="flex flex-wrap gap-3" role="radiogroup" aria-label="Tipo de owner">
          {OWNER_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className="inline-flex items-center gap-2 text-sm"
            >
              <input
                type="radio"
                name="owner_type"
                value={opt.value}
                checked={ownerType === opt.value}
                onChange={() => setOwnerType(opt.value)}
                disabled={isSaving}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </fieldset>

      {showDnRange && (
        <div className="grid grid-cols-2 gap-3" data-testid="dn-range-fields">
          <div className="space-y-1.5">
            <Label htmlFor="compat-dn-min">DN min</Label>
            <Input
              id="compat-dn-min"
              name="dn_min"
              type="number"
              min={0}
              max={10000}
              value={dnMin}
              onChange={(e) => setDnMin(e.target.value)}
              disabled={isSaving}
              placeholder="ej. 15"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="compat-dn-max">DN max</Label>
            <Input
              id="compat-dn-max"
              name="dn_max"
              type="number"
              min={0}
              max={10000}
              value={dnMax}
              onChange={(e) => setDnMax(e.target.value)}
              disabled={isSaving}
              placeholder="ej. 50"
            />
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="compat-notes">Notas</Label>
        <Input
          id="compat-notes"
          name="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSaving}
          placeholder="Opcional"
        />
      </div>

      {displayError ? (
        <p role="alert" className="text-sm text-destructive">
          {displayError}
        </p>
      ) : null}

      <Button type="submit" disabled={isSaving}>
        {isSaving ? "Guardando…" : "Añadir enlace"}
      </Button>
    </form>
  );
}

export default SparePartCompatibilityForm;
