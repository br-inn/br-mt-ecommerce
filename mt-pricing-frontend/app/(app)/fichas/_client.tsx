"use client";

import * as React from "react";
import { toast } from "sonner";
import { UploadCloud, RefreshCw, CheckCircle2, Plus, AlertTriangle, ChevronLeft } from "lucide-react";
import { MtButton, Pill, SectionCard } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";
import { EnrichmentDiffTable } from "@/components/domain/ficha-enrichment/enrichment-diff-table";
import {
  usePreviewFichaSeries,
  useApplyFichaSeries,
} from "@/lib/hooks/ficha-enrichment/use-ficha-enrich";
import type {
  FichaSeriesPreviewResponse,
  FichaSeriesApplyResponse,
} from "@/lib/api/endpoints/ficha-enrich";

const SCALAR_FIELDS = [
  "family", "subfamily", "type", "material", "dn", "pn", "connection", "brand",
  "weight", "weight_unit", "temp_min_c", "temp_max_c", "pressure_max_bar", "size",
] as const;

// ---------------------------------------------------------------------------
// Step 0: Dropzone
// ---------------------------------------------------------------------------
function Dropzone({ onFile, isPending, error }: {
  onFile: (f: File) => void;
  isPending: boolean;
  error: Error | null;
}) {
  const ref = React.useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = React.useState(false);

  return (
    <div className="flex flex-col items-center gap-6 py-16">
      <button
        type="button"
        disabled={isPending}
        onClick={() => ref.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files[0];
          if (f) onFile(f);
        }}
        className="flex w-full max-w-lg flex-col items-center gap-4 rounded-xl border-2 border-dashed px-8 py-12 transition-colors disabled:opacity-60"
        style={{
          borderColor: dragOver ? MT.brand : MT.borderStrong,
          backgroundColor: dragOver ? MT.brandSofter : MT.surface2,
        }}
        aria-label="Subir ficha técnica PDF"
      >
        {isPending
          ? <RefreshCw className="animate-spin" style={{ color: MT.brand }} size={36} strokeWidth={1.5} />
          : <UploadCloud size={36} strokeWidth={1.5} style={{ color: dragOver ? MT.brand : MT.ink3 }} />
        }
        <div className="text-center">
          <p className="text-[14px] font-semibold" style={{ color: MT.ink }}>
            {isPending ? "Analizando con Claude…" : "Arrastra o selecciona la ficha técnica PDF"}
          </p>
          <p className="text-[12px] mt-1" style={{ color: MT.ink3 }}>
            Formato: MTFT_XXXX.pdf — máx. 50 MB
          </p>
        </div>
      </button>
      <input
        ref={ref}
        type="file"
        accept="application/pdf"
        className="sr-only"
        aria-label="Subir ficha técnica PDF"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
      />
      {error && (
        <div
          className="flex w-full max-w-lg items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}
        >
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{error.message}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Serie review
// ---------------------------------------------------------------------------
function SerieStep({ preview, onReset, onApplySuccess }: {
  preview: FichaSeriesPreviewResponse;
  onReset: () => void;
  onApplySuccess: (result: FichaSeriesApplyResponse) => void;
}) {
  const applyMutation = useApplyFichaSeries();

  const firstSkuDiffs = preview.series_skus[0]?.diffs ?? [];
  const changedFields = React.useMemo(
    () => new Set(firstSkuDiffs.filter(d => d.has_change).map(d => d.field_name)),
    [firstSkuDiffs],
  );
  const [selectedFields, setSelectedFields] = React.useState<Set<string>>(changedFields);
  const [selectedSkus, setSelectedSkus] = React.useState<Set<string>>(
    () => new Set(preview.series_skus.map(s => s.sku)),
  );

  const toggleSku = (sku: string) => setSelectedSkus(prev => {
    const next = new Set(prev);
    next.has(sku) ? next.delete(sku) : next.add(sku);
    return next;
  });

  const toggleField = React.useCallback((f: string) => setSelectedFields(prev => {
    const next = new Set(prev);
    next.has(f) ? next.delete(f) : next.add(f);
    return next;
  }), []);

  const toggleAll = () => {
    if (selectedFields.size === changedFields.size) {
      setSelectedFields(new Set());
    } else {
      setSelectedFields(new Set(changedFields));
    }
  };

  const existingCount = preview.series_skus.filter(s => s.status === "existing").length;
  const newCount = preview.series_skus.filter(s => s.status === "new").length;

  const handleApply = () => {
    const scalarFields = [...selectedFields].filter(
      f => (SCALAR_FIELDS as readonly string[]).includes(f),
    );
    applyMutation.mutate({
      extraction: preview.extraction,
      apply_to_skus: [...selectedSkus],
      series: preview.series,
      pdf_filename: preview.filename,
      apply_scalars: scalarFields.length > 0,
      apply_specs: selectedFields.has("specs"),
      apply_materials: selectedFields.has("materials"),
      apply_dimensions: selectedFields.has("dimensions_by_dn"),
      apply_translations: selectedFields.has("translations"),
      selected_scalar_fields: scalarFields,
      save_document: true,
    }, {
      onSuccess: (result) => {
        toast.success(
          `Serie ${preview.series} procesada: ${result.skus_created.length} creados, ${result.skus_updated.length} actualizados`,
        );
        onApplySuccess(result);
      },
      onError: (err) => toast.error(err.message || "Error al aplicar"),
    });
  };

  const changedCount = firstSkuDiffs.filter(d => d.has_change).length;

  return (
    <div className="space-y-6">
      {/* Header */}
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
            <Pill tone="neutral" mono>{preview.page_count} págs</Pill>
            <Pill tone="brand" mono>Serie {preview.series}</Pill>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {existingCount > 0 && <Pill tone="neutral">{existingCount} existentes</Pill>}
          {newCount > 0 && <Pill tone="warning"><Plus size={10} />{newCount} nuevos</Pill>}
          {changedCount > 0 && (
            <MtButton tone="ghost" size="sm" onClick={toggleAll}>
              {selectedFields.size === changedFields.size ? "Deseleccionar todo" : "Seleccionar todo"}
            </MtButton>
          )}
          <MtButton
            tone="primary"
            size="md"
            disabled={selectedSkus.size === 0 || selectedFields.size === 0 || applyMutation.isPending}
            onClick={handleApply}
            icon={applyMutation.isPending ? <RefreshCw size={13} className="animate-spin" /> : undefined}
          >
            {applyMutation.isPending
              ? "Procesando…"
              : `Aplicar a ${selectedSkus.size} SKU${selectedSkus.size !== 1 ? "s" : ""} (${selectedFields.size} campos)`
            }
          </MtButton>
        </div>
      </div>

      {/* Model gaps */}
      {preview.model_gaps.length > 0 && (
        <div
          className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12px]"
          style={{ borderColor: MT.warningBorder, backgroundColor: MT.warningSoft, color: MT.warning }}
        >
          <AlertTriangle size={13} className="mt-px shrink-0" />
          <span><strong>Sin mapeo en modelo:</strong> {preview.model_gaps.join(", ")}</span>
        </div>
      )}

      {/* Apply error */}
      {applyMutation.isError && (
        <div
          className="flex items-start gap-2 rounded-lg border px-4 py-3 text-[12.5px]"
          style={{ borderColor: MT.dangerBorder, backgroundColor: MT.dangerSoft, color: MT.danger }}
        >
          <AlertTriangle size={14} className="mt-px shrink-0" />
          <span>{applyMutation.error.message}</span>
        </div>
      )}

      {/* SKU picker */}
      <SectionCard
        title={`SKUs en serie "${preview.series}" — ${preview.series_skus.length} detectados`}
      >
        <div className="px-4 py-3 flex flex-wrap gap-2">
          {preview.series_skus.map(s => {
            const isSelected = selectedSkus.has(s.sku);
            const diffCount = s.diffs.filter(d => d.has_change).length;
            return (
              <button
                key={s.sku}
                type="button"
                onClick={() => toggleSku(s.sku)}
                className="flex items-center gap-1.5 rounded border px-2.5 py-1 text-[12px] font-medium transition-colors"
                style={{
                  borderColor: isSelected ? MT.brand : MT.border,
                  backgroundColor: isSelected ? MT.brandSofter : MT.surface2,
                  color: isSelected ? MT.brand : MT.ink3,
                }}
              >
                <span className="mt-mono">{s.sku}</span>
                {s.status === "new" && (
                  <span
                    className="rounded px-1 text-[10px] font-semibold"
                    style={{ backgroundColor: MT.warningSoft, color: MT.warning }}
                  >
                    new
                  </span>
                )}
                {diffCount > 0 && (
                  <span style={{ color: MT.ink3 }}>({diffCount}↑)</span>
                )}
              </button>
            );
          })}
        </div>
      </SectionCard>

      {/* Diff table */}
      <SectionCard
        title="Diferencias campo a campo"
        subtitle={`${changedCount} campo${changedCount !== 1 ? "s" : ""} con cambios detectados`}
      >
        <div className="p-4">
          <EnrichmentDiffTable
            diffs={firstSkuDiffs}
            selectedFields={selectedFields}
            onToggleField={toggleField}
          />
        </div>
      </SectionCard>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2: Resultado
// ---------------------------------------------------------------------------
function ResultStep({ result, onReset }: {
  result: FichaSeriesApplyResponse;
  onReset: () => void;
}) {
  const hasWarnings = result.results.some(r => r.warnings.length > 0);

  return (
    <div className="flex flex-col items-center gap-6 py-12">
      <CheckCircle2
        size={48}
        strokeWidth={1.5}
        style={{ color: hasWarnings ? MT.warning : MT.success }}
      />
      <div className="text-center">
        <p className="text-[16px] font-semibold" style={{ color: MT.ink }}>
          {hasWarnings ? "Procesado con advertencias" : `Serie ${result.series} procesada`}
        </p>
        <p className="mt-1 text-[13px]" style={{ color: MT.ink3 }}>
          {result.skus_created.length > 0 && `${result.skus_created.length} SKUs creados · `}
          {result.skus_updated.length > 0 && `${result.skus_updated.length} SKUs actualizados`}
          {result.document_id && ` · Documento guardado`}
        </p>
      </div>

      <div className="w-full max-w-md space-y-2">
        {result.results.map(r => (
          <div
            key={r.sku}
            className="flex items-center justify-between rounded-lg border px-3 py-2 text-[12px]"
            style={{ borderColor: MT.border }}
          >
            <span className="mt-mono font-medium" style={{ color: MT.ink }}>{r.sku}</span>
            <div className="flex gap-1.5">
              {r.applied_fields.length > 0 && (
                <Pill tone="success" mono>{r.applied_fields.length} aplicados</Pill>
              )}
              {r.skipped_fields.length > 0 && (
                <Pill tone="neutral" mono>{r.skipped_fields.length} omitidos</Pill>
              )}
              {r.warnings.length > 0 && (
                <Pill tone="warning" mono>{r.warnings.length} avisos</Pill>
              )}
            </div>
          </div>
        ))}
      </div>

      <MtButton tone="neutral" size="md" onClick={onReset}>
        Subir otra ficha
      </MtButton>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------
export function FichasClient() {
  const previewMutation = usePreviewFichaSeries();
  const [applyResult, setApplyResult] = React.useState<FichaSeriesApplyResponse | null>(null);

  const reset = React.useCallback(() => {
    previewMutation.reset();
    setApplyResult(null);
  }, [previewMutation]);

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-[20px] font-semibold" style={{ color: MT.ink }}>Fichas técnicas</h1>
        <p className="text-[13px] mt-1" style={{ color: MT.ink3 }}>
          Sube una ficha técnica PDF para enriquecer o crear los productos de la serie.
        </p>
      </div>

      {applyResult ? (
        <ResultStep result={applyResult} onReset={reset} />
      ) : previewMutation.isSuccess ? (
        <SerieStep
          preview={previewMutation.data}
          onReset={reset}
          onApplySuccess={setApplyResult}
        />
      ) : (
        <Dropzone
          onFile={(f) => previewMutation.mutate(f)}
          isPending={previewMutation.isPending}
          error={previewMutation.error}
        />
      )}
    </div>
  );
}
