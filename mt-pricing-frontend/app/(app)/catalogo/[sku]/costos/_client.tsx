"use client";

/**
 * Tab "Costes" del producto — UI principal (US-1A-04-04).
 *
 * Reescrita en S3 vs el placeholder S2:
 * - Usa primitives `components/mt` (MtButton, MtTd, MtTh, Pill, MtSkeleton).
 * - `CostTable` por scheme × supplier con expand → breakdown desglosado.
 * - "Mostrar histórico" toggle (AC#4).
 * - Sheet ad-hoc (modal lateral con Headless approach minimal — sin shadcn
 *   para no acoplar) para crear/editar coste con `CostBreakdownEditor`.
 * - Maneja warnings del backend (campos no declarados → toast info).
 * - Maneja errores 422 (missing required field, fx_rate_not_found_at_effective_at).
 *
 * S4: templates de scheme se leen dinámicamente desde GET /api/v1/schemes
 * via `useSchemeTemplate`. Fallback hardcodeado en use-schemes.ts mientras carga.
 */

import * as React from "react";
import { toast } from "sonner";
import { X } from "lucide-react";

import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MtError } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { CostBreakdownEditor } from "@/components/domain/costs/cost-breakdown-editor";
import { CostTable } from "@/components/domain/costs/cost-table";
import {
  COST_SCHEMES,
  CostsApiError,
  type Cost,
  type CostBreakdown,
  type CostCreatePayload,
} from "@/lib/api/endpoints/costs";
import { SUPPLIER_CURRENCIES } from "@/lib/api/endpoints/suppliers";
import { useCostsForSku } from "@/lib/hooks/costs/use-costs";
import {
  useCloseCost,
  useCreateCost,
  useUpdateCost,
} from "@/lib/hooks/costs/use-cost-mutations";
import { useSchemeTemplate } from "@/lib/hooks/costs/use-schemes";

interface Props {
  sku: string;
}

// ---------------------------------------------------------------------------
// Los templates de componentes de coste se leen dinámicamente desde
// GET /api/v1/schemes via `useSchemeTemplate` (US-1A-04-S4).
// El fallback hardcodeado vive en lib/hooks/costs/use-schemes.ts
// y se usa automáticamente mientras carga o ante error de red.
// ---------------------------------------------------------------------------

export function CostsTabClient({ sku }: Props) {
  const { data: costs, isLoading, isError, refetch } = useCostsForSku(
    sku,
    undefined /* as_of: vigentes hoy */,
    false /* only_active=false → incluir histórico */,
  );
  const [showHistory, setShowHistory] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Cost | null>(null);
  const [closing, setClosing] = React.useState<Cost | null>(null);

  const handleAdd = () => {
    setEditing(null);
    setSheetOpen(true);
  };
  const handleEdit = (c: Cost) => {
    setEditing(c);
    setSheetOpen(true);
  };
  const handleCloseSheet = () => {
    setSheetOpen(false);
    setEditing(null);
  };
  const handleDescatalogar = (c: Cost) => setClosing(c);

  if (isError) {
    return (
      <SectionCard title="Costes por esquema">
        <div className="p-4">
          <MtError
            message="No se pudieron cargar los costes."
            onRetry={() => refetch()}
          />
        </div>
      </SectionCard>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <CostTable
        costs={costs ?? []}
        loading={isLoading}
        onAdd={handleAdd}
        onEdit={handleEdit}
        onClose={handleDescatalogar}
        showHistory={showHistory}
        onToggleHistory={setShowHistory}
        canWrite
      />

      {sheetOpen ? (
        <RbacGuard permissions={["costs:write"]}>
          <CostFormSheet
            sku={sku}
            initial={editing}
            onClose={handleCloseSheet}
            onSaved={() => {
              handleCloseSheet();
              void refetch();
            }}
          />
        </RbacGuard>
      ) : null}

      {closing ? (
        <RbacGuard permissions={["costs:write"]}>
          <CloseCostDialog
            cost={closing}
            onCancel={() => setClosing(null)}
            onClosed={() => {
              setClosing(null);
              void refetch();
            }}
          />
        </RbacGuard>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CostFormSheet — sheet lateral modal (no shadcn — primitives + plain CSS)
// ---------------------------------------------------------------------------
function CostFormSheet({
  sku,
  initial,
  onClose,
  onSaved,
}: {
  sku: string;
  initial: Cost | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial;
  const initialScheme =
    (initial?.scheme_code as (typeof COST_SCHEMES)[number]) ?? "FBA";
  const [schemeCode, setSchemeCode] = React.useState<
    (typeof COST_SCHEMES)[number]
  >(initialScheme);
  const [supplier, setSupplier] = React.useState(initial?.supplier_code ?? "");
  const [currencyOrigin, setCurrencyOrigin] = React.useState(
    initial?.currency_origin ?? "EUR",
  );
  const [validFrom, setValidFrom] = React.useState<string>(
    () => initial?.valid_from ?? new Date().toISOString().slice(0, 10),
  );
  const [breakdown, setBreakdown] = React.useState<CostBreakdown>(
    initial?.breakdown ?? {},
  );
  const [fieldErrors, setFieldErrors] = React.useState<Record<string, string>>(
    {},
  );
  const [topLevelError, setTopLevelError] = React.useState<string | null>(null);

  const createMut = useCreateCost();
  const updateMut = useUpdateCost(initial?.id ?? "");

  const template = useSchemeTemplate(schemeCode);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setTopLevelError(null);
    try {
      if (isEdit && initial) {
        const resp = await updateMut.mutateAsync({
          breakdown,
          valid_from: validFrom,
          currency_origin: currencyOrigin,
        });
        toast.success("Coste corregido.");
        if (resp.warnings.length) {
          toast.message(
            `Aviso: ${resp.warnings.length} campo(s) no declarado(s).`,
          );
        }
        onSaved();
        return;
      }
      const payload: CostCreatePayload = {
        sku,
        scheme_code: schemeCode,
        supplier_code: supplier ? supplier : null,
        currency_origin: currencyOrigin,
        valid_from: validFrom,
        breakdown,
      };
      const resp = await createMut.mutateAsync(payload);
      toast.success("Coste creado.");
      if (resp.warnings.length) {
        toast.message(
          `Aviso: ${resp.warnings.length} campo(s) no declarado(s).`,
        );
      }
      onSaved();
    } catch (err) {
      if (err instanceof CostsApiError) {
        const detail = err.detail as Record<string, unknown> | undefined;
        const inner = detail?.detail as Record<string, unknown> | undefined;
        const code = inner?.code ?? detail?.code;
        const fieldName = inner?.field ?? detail?.field;
        if (code === "missing_required_breakdown_field" && fieldName) {
          setFieldErrors({
            [String(fieldName)]: "Campo requerido por el scheme",
          });
          setTopLevelError("Faltan campos requeridos en el breakdown.");
          return;
        }
        if (code === "fx_rate_not_found_at_effective_at") {
          setTopLevelError(
            `No hay tasa de cambio ${currencyOrigin}→AED a la fecha indicada.`,
          );
          return;
        }
        setTopLevelError(
          (typeof inner?.title === "string" && inner.title) ||
            (typeof detail?.title === "string" && detail.title) ||
            err.message,
        );
        return;
      }
      setTopLevelError(err instanceof Error ? err.message : "Error desconocido");
    }
  };

  const isPending = createMut.isPending || updateMut.isPending;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
        onClick={onClose}
        aria-hidden
        data-testid="cost-sheet-backdrop"
      />
      {/* Sheet */}
      <aside
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col gap-4 overflow-y-auto border-l p-5"
        style={{ backgroundColor: MT.surface, borderColor: MT.border }}
        role="dialog"
        aria-modal="true"
        aria-label={isEdit ? "Corregir coste" : "Nuevo coste desde fecha"}
        data-testid="cost-sheet"
      >
        <header className="flex items-center justify-between">
          <h2 className="text-[16px] font-semibold" style={{ color: MT.ink }}>
            {isEdit ? "Corregir coste" : "Nuevo coste desde fecha"}
          </h2>
          <MtButton
            size="sm"
            tone="ghost"
            icon={<X className="size-3.5" />}
            onClick={onClose}
            aria-label="Cerrar"
          />
        </header>

        {topLevelError ? (
          <div
            className="rounded-md border px-3 py-2 text-[12.5px]"
            style={{
              backgroundColor: MT.dangerSoft,
              borderColor: MT.dangerBorder,
              color: MT.danger,
            }}
            data-testid="cost-form-error"
          >
            {topLevelError}
          </div>
        ) : null}

        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <div className="grid grid-cols-2 gap-3">
            <FieldLabel label="Scheme">
              <select
                value={schemeCode}
                onChange={(e) =>
                  setSchemeCode(
                    e.target.value as (typeof COST_SCHEMES)[number],
                  )
                }
                disabled={isEdit}
                className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
                style={{ borderColor: MT.border }}
                data-testid="cost-scheme"
              >
                {COST_SCHEMES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <FieldLabel label="Supplier (opcional)">
              <input
                type="text"
                value={supplier}
                onChange={(e) => setSupplier(e.target.value)}
                disabled={isEdit}
                placeholder="MT_VALVES_ES"
                className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
                style={{ borderColor: MT.border }}
                data-testid="cost-supplier"
              />
            </FieldLabel>

            <FieldLabel label="Moneda origen">
              <select
                value={currencyOrigin}
                onChange={(e) => setCurrencyOrigin(e.target.value)}
                className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
                style={{ borderColor: MT.border }}
                data-testid="cost-currency-origin"
              >
                {SUPPLIER_CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </FieldLabel>

            <FieldLabel label="Vigente desde">
              <input
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
                style={{ borderColor: MT.border }}
                data-testid="cost-valid-from"
              />
            </FieldLabel>
          </div>

          <div className="flex items-center justify-between">
            <span
              className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
              style={{ color: MT.ink3 }}
            >
              Breakdown
            </span>
            <Pill tone="neutral">{schemeCode}</Pill>
          </div>

          <CostBreakdownEditor
            breakdown={breakdown}
            required={template.required}
            optional={template.optional}
            errors={fieldErrors}
            onChange={setBreakdown}
            disabled={isPending}
          />

          <footer className="mt-2 flex items-center justify-end gap-2">
            <MtButton tone="ghost" onClick={onClose} disabled={isPending}>
              Cancelar
            </MtButton>
            <MtButton
              tone="primary"
              type="submit"
              disabled={isPending}
              data-testid="cost-submit"
            >
              {isPending ? "Guardando…" : isEdit ? "Guardar corrección" : "Crear coste"}
            </MtButton>
          </footer>
        </form>
      </aside>
    </>
  );
}

// ---------------------------------------------------------------------------
// CloseCostDialog — descatalogar (fijar valid_to) el coste vigente.
// Modal pequeño y centrado, consistente con el estilo del sheet (primitives).
// ---------------------------------------------------------------------------
function CloseCostDialog({
  cost,
  onCancel,
  onClosed,
}: {
  cost: Cost;
  onCancel: () => void;
  onClosed: () => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [validTo, setValidTo] = React.useState<string>(today);
  const [error, setError] = React.useState<string | null>(null);
  const closeMut = useCloseCost();

  const handleConfirm = async () => {
    setError(null);
    if (validTo < cost.valid_from) {
      setError("La fecha de cierre no puede ser anterior a la fecha de inicio.");
      return;
    }
    try {
      await closeMut.mutateAsync({ id: cost.id, valid_to: validTo });
      toast.success("Coste descatalogado.");
      onClosed();
    } catch (err) {
      if (err instanceof CostsApiError) {
        const detail = err.detail as Record<string, unknown> | undefined;
        const inner = detail?.detail as Record<string, unknown> | undefined;
        setError(
          (typeof inner?.title === "string" && inner.title) ||
            (typeof detail?.title === "string" && detail.title) ||
            err.message,
        );
        return;
      }
      setError(err instanceof Error ? err.message : "Error desconocido");
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40"
        style={{ backgroundColor: "rgba(0,0,0,0.35)" }}
        onClick={onCancel}
        aria-hidden
        data-testid="cost-close-backdrop"
      />
      <div
        className="fixed left-1/2 top-1/2 z-50 flex w-full max-w-sm -translate-x-1/2 -translate-y-1/2 flex-col gap-3 rounded-lg border p-5"
        style={{ backgroundColor: MT.surface, borderColor: MT.border }}
        role="dialog"
        aria-modal="true"
        aria-label="Descatalogar coste"
        data-testid="cost-close-dialog"
      >
        <header className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold" style={{ color: MT.ink }}>
            Descatalogar coste
          </h2>
          <MtButton
            size="sm"
            tone="ghost"
            icon={<X className="size-3.5" />}
            onClick={onCancel}
            aria-label="Cerrar"
          />
        </header>

        <p className="text-[12.5px]" style={{ color: MT.ink2 }}>
          Se fijará la fecha de fin de vigencia (<span className="mt-mono">{cost.scheme_code}</span>
          {cost.supplier_code ? ` · ${cost.supplier_code}` : ""}). El coste deja
          de estar vigente a partir de esa fecha.
        </p>

        {error ? (
          <div
            className="rounded-md border px-3 py-2 text-[12.5px]"
            style={{
              backgroundColor: MT.dangerSoft,
              borderColor: MT.dangerBorder,
              color: MT.danger,
            }}
            data-testid="cost-close-error"
          >
            {error}
          </div>
        ) : null}

        <FieldLabel label="Vigente hasta">
          <input
            type="date"
            value={validTo}
            min={cost.valid_from}
            onChange={(e) => setValidTo(e.target.value)}
            className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
            style={{ borderColor: MT.border }}
            data-testid="cost-close-valid-to"
          />
        </FieldLabel>

        <footer className="mt-1 flex items-center justify-end gap-2">
          <MtButton
            tone="ghost"
            onClick={onCancel}
            disabled={closeMut.isPending}
          >
            Cancelar
          </MtButton>
          <MtButton
            tone="danger"
            onClick={handleConfirm}
            disabled={closeMut.isPending}
            data-testid="cost-close-confirm"
          >
            {closeMut.isPending ? "Descatalogando…" : "Descatalogar"}
          </MtButton>
        </footer>
      </div>
    </>
  );
}

function FieldLabel({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span
        className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
        style={{ color: MT.ink3 }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}

export default CostsTabClient;
