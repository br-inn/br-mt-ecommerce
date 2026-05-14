"use client";

import * as React from "react";
import { UploadCloud, CheckCircle2, AlertTriangle, ChevronLeft, RefreshCw } from "lucide-react";

import { EnrichmentDiffTable } from "@/components/domain/ficha-enrichment/enrichment-diff-table";
import { usePreviewFichaEnrich, useApplyFichaEnrich } from "@/lib/hooks/ficha-enrichment/use-ficha-enrich";
import type { FichaEnrichPreviewResponse } from "@/lib/api/endpoints/ficha-enrich";
import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SCALAR_FIELDS = [
  "family",
  "subfamily",
  "type",
  "material",
  "dn",
  "pn",
  "connection",
  "brand",
  "weight",
  "weight_unit",
  "temp_min_c",
  "temp_max_c",
  "pressure_max_bar",
  "size",
] as const;

// ---------------------------------------------------------------------------
// Step 0: Dropzone
// ---------------------------------------------------------------------------

interface DropzoneProps {
  onFile: (file: File) => void;
  isPending: boolean;
  error: Error | null;
}

function Dropzone({ onFile, isPending, error }: DropzoneProps) {
  const [dragOver, setDragOver] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  };

  return (
    <div className="flex flex-col items-center gap-6 py-12">
      <button
        type="button"
        disabled={isPending}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className="flex w-full max-w-lg flex-col items-center gap-4 rounded-xl border-2 border-dashed px-8 py-10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        style={{
          borderColor: dragOver ? MT.brand : MT.borderStrong,
          backgroundColor: dragOver ? MT.brandSofter : MT.surface2,
        }}
        aria-label="Subir ficha técnica PDF"
      >
        {isPending ? (
          <RefreshCw
            className="animate-spin"
            style={{ color: MT.brand }}
            size={32}
            strokeWidth={1.5}
          />
        ) : (
          <UploadCloud
            size={32}
            strokeWidth={1.5}
            style={{ color: dragOver ? MT.brand : MT.ink3 }}
          />
        )}
        <div className="flex flex-col items-center gap-1 text-center">
          <span className="text-[13.5px] font-semibold" style={{ color: MT.ink }}>
            {isPending ? "Analizando PDF…" : "Arrastra un PDF o haz clic para seleccionar"}
          </span>
          <span className="text-[12px]" style={{ color: MT.ink3 }}>
            Ficha técnica del producto en PDF (máx. 50 MB)
          </span>
        </div>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="sr-only"
        onChange={handleChange}
      />

      {error ? (
        <div
          className="flex w-full max-w-lg items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}
        >
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{error.message}</span>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Diff review + apply
// ---------------------------------------------------------------------------

interface DiffStepProps {
  sku: string;
  preview: FichaEnrichPreviewResponse;
  onReset: () => void;
}

function DiffStep({ sku, preview, onReset }: DiffStepProps) {
  const applyMutation = useApplyFichaEnrich(sku);

  // Auto-select all changed diffs on mount
  const changedFields = React.useMemo(
    () => new Set(preview.diffs.filter((d) => d.has_change).map((d) => d.field_name)),
    [preview.diffs],
  );
  const [selectedFields, setSelectedFields] = React.useState<Set<string>>(changedFields);

  const toggle = React.useCallback((fieldName: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev);
      if (next.has(fieldName)) {
        next.delete(fieldName);
      } else {
        next.add(fieldName);
      }
      return next;
    });
  }, []);

  const toggleAll = () => {
    if (selectedFields.size === changedFields.size) {
      setSelectedFields(new Set());
    } else {
      setSelectedFields(new Set(changedFields));
    }
  };

  const handleApply = () => {
    const selectedScalarFields = [...selectedFields].filter((f) =>
      (SCALAR_FIELDS as readonly string[]).includes(f),
    );
    const hasSpec = selectedFields.has("specs");
    const hasMaterials = selectedFields.has("materials");
    const hasDimensions = selectedFields.has("dimensions_by_dn");
    const hasTranslations = selectedFields.has("translations");

    applyMutation.mutate({
      extraction: preview.extraction,
      apply_scalars: selectedScalarFields.length > 0,
      apply_specs: hasSpec,
      apply_materials: hasMaterials,
      apply_dimensions: hasDimensions,
      apply_translations: hasTranslations,
      selected_scalar_fields: selectedScalarFields,
    });
  };

  if (applyMutation.isSuccess) {
    return <ResultStep result={applyMutation.data} onReset={onReset} />;
  }

  const changedCount = preview.diffs.filter((d) => d.has_change).length;

  return (
    <div className="space-y-5">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MtButton tone="ghost" size="sm" icon={<ChevronLeft size={13} />} onClick={onReset}>
            Cambiar PDF
          </MtButton>
          <div className="flex items-center gap-2">
            <span className="mt-mono text-[11.5px]" style={{ color: MT.ink3 }}>
              {preview.filename}
            </span>
            <Pill tone={preview.confidence >= 0.7 ? "success" : preview.confidence >= 0.4 ? "warning" : "danger"} dot>
              {Math.round(preview.confidence * 100)}% confianza
            </Pill>
            <Pill tone="neutral" mono>
              {preview.page_count} págs
            </Pill>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {changedCount > 0 ? (
            <MtButton tone="ghost" size="sm" onClick={toggleAll}>
              {selectedFields.size === changedFields.size ? "Deseleccionar todo" : "Seleccionar todo"}
            </MtButton>
          ) : null}
          <MtButton
            tone="primary"
            size="md"
            disabled={selectedFields.size === 0 || applyMutation.isPending}
            onClick={handleApply}
            icon={applyMutation.isPending ? <RefreshCw size={13} className="animate-spin" /> : undefined}
          >
            {applyMutation.isPending ? "Aplicando…" : `Aplicar ${selectedFields.size} campo${selectedFields.size !== 1 ? "s" : ""}`}
          </MtButton>
        </div>
      </div>

      {/* Model gaps */}
      {preview.model_gaps.length > 0 ? (
        <div
          className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12px]"
          style={{ borderColor: MT.warningBorder, backgroundColor: MT.warningSoft, color: MT.warning }}
        >
          <AlertTriangle size={13} className="mt-px shrink-0" />
          <div>
            <span className="font-semibold">Campos no extraídos: </span>
            {preview.model_gaps.join(", ")}
          </div>
        </div>
      ) : null}

      {/* Apply error */}
      {applyMutation.isError ? (
        <div
          className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}
        >
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{applyMutation.error.message}</span>
        </div>
      ) : null}

      {/* Diff table */}
      <SectionCard
        title="Diferencias campo a campo"
        subtitle={`${changedCount} campo${changedCount !== 1 ? "s" : ""} con cambios detectados`}
      >
        <div className="p-4">
          <EnrichmentDiffTable
            diffs={preview.diffs}
            selectedFields={selectedFields}
            onToggleField={toggle}
          />
        </div>
      </SectionCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2: Result
// ---------------------------------------------------------------------------

interface ResultStepProps {
  result: { applied_fields: string[]; skipped_fields: string[]; errors: string[] };
  onReset: () => void;
}

function ResultStep({ result, onReset }: ResultStepProps) {
  const hasErrors = result.errors.length > 0;

  return (
    <div className="flex flex-col items-center gap-6 py-10">
      <div className="flex flex-col items-center gap-3 text-center">
        <CheckCircle2
          size={40}
          strokeWidth={1.5}
          style={{ color: hasErrors ? MT.warning : MT.success }}
        />
        <div>
          <p className="text-[15px] font-semibold" style={{ color: MT.ink }}>
            {hasErrors ? "Aplicado con advertencias" : "Enriquecimiento aplicado"}
          </p>
          <p className="mt-1 text-[12.5px]" style={{ color: MT.ink3 }}>
            {result.applied_fields.length} campo{result.applied_fields.length !== 1 ? "s" : ""} actualizados
            {result.skipped_fields.length > 0
              ? `, ${result.skipped_fields.length} omitido${result.skipped_fields.length !== 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
      </div>

      {/* Applied fields */}
      {result.applied_fields.length > 0 ? (
        <div className="w-full max-w-md">
          <SectionCard title="Campos aplicados">
            <div className="flex flex-wrap gap-1.5 p-4">
              {result.applied_fields.map((f) => (
                <Pill key={f} tone="success" mono>
                  {f}
                </Pill>
              ))}
            </div>
          </SectionCard>
        </div>
      ) : null}

      {/* Skipped fields */}
      {result.skipped_fields.length > 0 ? (
        <div className="w-full max-w-md">
          <SectionCard title="Campos omitidos">
            <div className="flex flex-wrap gap-1.5 p-4">
              {result.skipped_fields.map((f) => (
                <Pill key={f} tone="neutral" mono>
                  {f}
                </Pill>
              ))}
            </div>
          </SectionCard>
        </div>
      ) : null}

      {/* Errors */}
      {result.errors.length > 0 ? (
        <div
          className="w-full max-w-md rounded-lg border px-4 py-3"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft }}
        >
          <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-[0.5px]" style={{ color: MT.danger }}>
            Errores
          </p>
          <ul className="space-y-1">
            {result.errors.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-[12px]" style={{ color: MT.danger }}>
                <AlertTriangle size={12} className="mt-px shrink-0" />
                {e}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <MtButton tone="neutral" size="md" onClick={onReset}>
        Enriquecer con otro PDF
      </MtButton>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root wizard
// ---------------------------------------------------------------------------

interface FichaEnrichClientProps {
  sku: string;
}

export function FichaEnrichClient({ sku }: FichaEnrichClientProps) {
  const previewMutation = usePreviewFichaEnrich(sku);

  const reset = React.useCallback(() => {
    previewMutation.reset();
  }, [previewMutation]);

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center gap-3">
        {(["1. Subir PDF", "2. Revisar cambios", "3. Resultado"] as const).map((label, i) => {
          const active =
            i === 0
              ? !previewMutation.isSuccess
              : i === 1
                ? previewMutation.isSuccess
                : false;
          return (
            <React.Fragment key={label}>
              {i > 0 ? (
                <span
                  className="h-px flex-1"
                  style={{ backgroundColor: MT.border, maxWidth: "2rem" }}
                />
              ) : null}
              <span
                className="mt-sans text-[12px] font-medium whitespace-nowrap"
                style={{ color: active ? MT.brand : MT.ink3 }}
              >
                {label}
              </span>
            </React.Fragment>
          );
        })}
      </div>

      {/* Step content */}
      {previewMutation.isSuccess ? (
        <DiffStep sku={sku} preview={previewMutation.data} onReset={reset} />
      ) : (
        <Dropzone
          onFile={(file) => previewMutation.mutate(file)}
          isPending={previewMutation.isPending}
          error={previewMutation.error}
        />
      )}
    </div>
  );
}
