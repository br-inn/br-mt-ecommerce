"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils/cn";
import {
  useApplyImport,
  useImportStatus,
  useUploadImport,
} from "@/lib/hooks/imports/use-imports";
import type {
  AnalyzeImportResponse,
  ColumnMappingItem,
  ImportPreview,
} from "@/lib/api/endpoints/imports";
import { divisionsApi, type Division } from "@/lib/api/endpoints/divisions";
import { UploadStep } from "./upload-step";
import { MappingStep } from "./mapping-step";
import { PreviewDiff } from "./preview-diff";
import { ApplyProgress } from "./apply-progress";
import { ImportReportPanel } from "./import-report";

type Step = 0 | 1 | 2 | 3 | 4;

/**
 * Wizard 5 pasos del importer PIM (US-1A-06-01 frontend half).
 * State machine: upload → mapping → preview → confirm → applying/report.
 * Polling 2s sobre `/imports/{id}/status` mientras `applying`.
 */
export function ImportWizard() {
  const t = useTranslations("imports.wizard");
  const tCommon = useTranslations("common");
  const [step, setStep] = React.useState<Step>(0);
  const [analysis, setAnalysis] = React.useState<AnalyzeImportResponse | null>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [confirmedMapping, setConfirmedMapping] = React.useState<ColumnMappingItem[] | null>(null);
  const [preview, setPreview] = React.useState<ImportPreview | null>(null);
  const [applyTriggered, setApplyTriggered] = React.useState(false);
  // Stage 3 (Wave 11) — override de divisiones a asignar por SKU del run.
  const [divisionCodes, setDivisionCodes] = React.useState<string[]>([]);

  const uploadPreview = useUploadImport();
  const apply = useApplyImport();
  // Polling sólo cuando el step es "applying" (4) y tenemos run_id.
  const status = useImportStatus(preview?.run_id, step === 4 && !!preview);

  // Cuando llega status terminal completed/failed, ya no avanzamos step
  // pero render cambia (ImportReport) basado en status.data.
  React.useEffect(() => {
    if (
      status.data?.status === "completed" ||
      status.data?.status === "failed" ||
      status.data?.status === "cancelled"
    ) {
      // estamos ya en step 4, sólo render del report
    }
  }, [status.data?.status]);

  const handleAnalyzed = (a: AnalyzeImportResponse, f: File) => {
    setAnalysis(a);
    setFile(f);
    setStep(1);
  };

  const handleMappingConfirmed = async (mapping: ColumnMappingItem[]) => {
    if (!file) {
      toast.error(tCommon("error"));
      return;
    }
    setConfirmedMapping(mapping);
    try {
      const p = await uploadPreview.mutateAsync({ file, mapping });
      setPreview(p);
      setStep(2);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      await apply.mutateAsync({
        runId: preview.run_id,
        division_codes: divisionCodes.length > 0 ? divisionCodes : null,
      });
      setApplyTriggered(true);
      setStep(4);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleReset = () => {
    setAnalysis(null);
    setFile(null);
    setConfirmedMapping(null);
    setPreview(null);
    setApplyTriggered(false);
    setStep(0);
  };

  const stepTitles = [t("step1"), t("stepMapping"), t("step2"), t("step3"), t("step4")];
  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "failed" ||
    status.data?.status === "cancelled";

  return (
    <div className="space-y-6" data-testid="import-wizard">
      <Stepper currentStep={step} stepTitles={stepTitles} />

      {step === 0 ? <UploadStep onAnalyzed={handleAnalyzed} /> : null}

      {step === 1 && analysis ? (
        <MappingStep
          analysis={analysis}
          onBack={() => setStep(0)}
          onConfirm={handleMappingConfirmed}
          isLoading={uploadPreview.isPending}
        />
      ) : null}

      {step === 2 && preview ? (
        <PreviewDiff
          preview={preview}
          onBack={() => setStep(1)}
          onConfirm={() => setStep(3)}
        />
      ) : null}

      {step === 3 && preview ? (
        <div className="space-y-4">
          <DivisionPicker selected={divisionCodes} onChange={setDivisionCodes} />
          <PreviewDiff
            preview={preview}
            onBack={() => setStep(2)}
            onConfirm={handleConfirm}
            isApplying={apply.isPending}
          />
        </div>
      ) : null}

      {step === 4 && preview ? (
        <div className="space-y-4">
          <ApplyProgress run={status.data} isLoading={!status.data || !applyTriggered} />
          {isTerminal && status.data ? (
            <ImportReportPanel run={status.data} onReset={handleReset} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Stepper({
  currentStep,
  stepTitles,
}: {
  currentStep: number;
  stepTitles: string[];
}) {
  return (
    <ol
      className="flex items-center gap-2 text-sm"
      role="list"
      aria-label="Stepper"
    >
      {stepTitles.map((title, idx) => {
        const done = idx < currentStep;
        const current = idx === currentStep;
        return (
          <li key={title} className="flex flex-1 items-center gap-2">
            <span
              aria-current={current ? "step" : undefined}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ring-2 ring-offset-2 ring-offset-background",
                done
                  ? "bg-primary text-primary-foreground ring-primary"
                  : current
                    ? "bg-primary/10 text-primary ring-primary"
                    : "bg-muted text-muted-foreground ring-transparent",
              )}
            >
              {done ? <Check className="h-3 w-3" /> : idx + 1}
            </span>
            <span
              className={cn(
                "hidden text-xs font-medium md:inline",
                current ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {title}
            </span>
            {idx < stepTitles.length - 1 ? (
              <span className="h-px flex-1 bg-border" aria-hidden />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

// ----------------------------------------------------------------------------
// Stage 3 (Wave 11) — DivisionPicker
// ----------------------------------------------------------------------------

function DivisionPicker({
  selected,
  onChange,
}: {
  selected: string[];
  onChange: (codes: string[]) => void;
}) {
  const divisionsQ = useQuery({
    queryKey: ["divisions", "public"],
    queryFn: () => divisionsApi.listPublic(),
    staleTime: 5 * 60_000,
  });

  const toggle = (code: string) => {
    if (selected.includes(code)) {
      onChange(selected.filter((c) => c !== code));
    } else {
      onChange([...selected, code]);
    }
  };

  return (
    <div className="rounded-md border bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Asignar a divisiones</h3>
        <span className="text-xs text-muted-foreground">
          {selected.length === 0 ? "default backend (PIM_DEFAULT_DIVISIONS)" : `${selected.length} seleccionada(s)`}
        </span>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Los SKUs creados o actualizados por este run se enlazarán a las divisiones
        seleccionadas. Si no seleccionas ninguna, se usa la configuración por defecto del servidor.
      </p>
      {divisionsQ.isLoading ? (
        <div className="text-xs text-muted-foreground">Cargando divisiones…</div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {(divisionsQ.data ?? []).map((d: Division) => {
            const isSelected = selected.includes(d.code);
            return (
              <button
                key={d.code}
                type="button"
                onClick={() => toggle(d.code)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition-colors",
                  isSelected
                    ? "bg-primary text-primary-foreground"
                    : "bg-background hover:bg-accent",
                )}
              >
                {d.name}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
