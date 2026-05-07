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
 * Nota: placeholders de scheme template — en S3 no consumimos el endpoint de
 * schemes con `cost_components_template` (defer a S4). Hardcodeamos el
 * mapping inicial de los 5 esquemas para el editor; el backend valida.
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
  useCreateCost,
  useUpdateCost,
} from "@/lib/hooks/costs/use-cost-mutations";

interface Props {
  sku: string;
}

// ---------------------------------------------------------------------------
// Hardcoded scheme component templates — en S4 leeremos /api/v1/schemes.
// ---------------------------------------------------------------------------
const SCHEME_TEMPLATES: Record<
  (typeof COST_SCHEMES)[number],
  { required: string[]; optional: string[] }
> = {
  FBA: {
    required: ["fob_eur", "freight_eur", "customs_aed", "fba_fees_aed"],
    optional: ["payment_fees_pct", "marketing_aed", "storage_aed"],
  },
  FBM: {
    required: ["fob_eur", "freight_eur", "customs_aed", "fbm_fees_aed"],
    optional: ["payment_fees_pct", "marketing_aed"],
  },
  DIRECT_B2C: {
    required: ["fob_eur", "freight_eur", "customs_aed"],
    optional: ["payment_fees_pct", "marketing_aed", "shipping_aed"],
  },
  DIRECT_B2B: {
    required: ["fob_eur", "freight_eur", "customs_aed"],
    optional: ["payment_fees_pct"],
  },
  MARKETPLACE: {
    required: ["fob_eur", "freight_eur", "customs_aed", "marketplace_fees_pct"],
    optional: ["payment_fees_pct", "marketing_aed"],
  },
};

export function CostsTabClient({ sku }: Props) {
  const { data: costs, isLoading, isError, refetch } = useCostsForSku(
    sku,
    false /* incluir histórico */,
  );
  const [showHistory, setShowHistory] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Cost | null>(null);

  const handleAdd = () => {
    setEditing(null);
    setSheetOpen(true);
  };
  const handleEdit = (c: Cost) => {
    setEditing(c);
    setSheetOpen(true);
  };
  const handleClose = () => {
    setSheetOpen(false);
    setEditing(null);
  };

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
        showHistory={showHistory}
        onToggleHistory={setShowHistory}
        canWrite
      />

      {sheetOpen ? (
        <RbacGuard permissions={["costs:write"]}>
          <CostFormSheet
            sku={sku}
            initial={editing}
            onClose={handleClose}
            onSaved={() => {
              handleClose();
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
  const [effectiveAt, setEffectiveAt] = React.useState<string>(
    () =>
      initial?.effective_at?.slice(0, 10) ??
      new Date().toISOString().slice(0, 10),
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

  const template = SCHEME_TEMPLATES[schemeCode];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});
    setTopLevelError(null);
    try {
      if (isEdit && initial) {
        const resp = await updateMut.mutateAsync({
          breakdown,
          effective_at: new Date(effectiveAt + "T00:00:00Z").toISOString(),
          currency_origin: currencyOrigin,
        });
        toast.success(`Versión ${resp.cost.version} creada.`);
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
        effective_at: new Date(effectiveAt + "T00:00:00Z").toISOString(),
        breakdown,
      };
      const resp = await createMut.mutateAsync(payload);
      toast.success(`Coste creado (v${resp.cost.version}).`);
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
        aria-label={isEdit ? "Editar coste" : "Nuevo coste"}
        data-testid="cost-sheet"
      >
        <header className="flex items-center justify-between">
          <h2 className="text-[16px] font-semibold" style={{ color: MT.ink }}>
            {isEdit ? "Editar coste" : "Nuevo coste"}
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

            <FieldLabel label="Effective at">
              <input
                type="date"
                value={effectiveAt}
                onChange={(e) => setEffectiveAt(e.target.value)}
                className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
                style={{ borderColor: MT.border }}
                data-testid="cost-effective-at"
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
              {isPending ? "Guardando…" : isEdit ? "Crear nueva versión" : "Crear coste"}
            </MtButton>
          </footer>
        </form>
      </aside>
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
