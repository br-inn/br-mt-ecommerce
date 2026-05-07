"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Check } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils/cn";
import {
  useApplyImport,
  useImportStatus,
} from "@/lib/hooks/imports/use-imports";
import type { ImportPreview } from "@/lib/api/endpoints/imports";
import { UploadStep } from "./upload-step";
import { PreviewDiff } from "./preview-diff";
import { ApplyProgress } from "./apply-progress";
import { ImportReportPanel } from "./import-report";

type Step = 0 | 1 | 2 | 3;

/**
 * Wizard 4 pasos del importer PIM (US-1A-06-01 frontend half).
 * State machine: upload → preview → applying → report.
 * Polling 2s sobre `/imports/{id}/status` mientras `applying`.
 */
export function ImportWizard() {
  const t = useTranslations("imports.wizard");
  const tCommon = useTranslations("common");
  const [step, setStep] = React.useState<Step>(0);
  const [preview, setPreview] = React.useState<ImportPreview | null>(null);
  const [applyTriggered, setApplyTriggered] = React.useState(false);

  const apply = useApplyImport();
  // Polling sólo cuando el step es "applying" (3) y tenemos run_id.
  const status = useImportStatus(preview?.id, step === 3 && !!preview);

  // Cuando llega status terminal completed/failed, ya no avanzamos step
  // pero render cambia (ImportReport) basado en status.data.
  React.useEffect(() => {
    if (
      status.data?.status === "completed" ||
      status.data?.status === "failed" ||
      status.data?.status === "cancelled"
    ) {
      // estamos ya en step 3, sólo render del report
    }
  }, [status.data?.status]);

  const handleUploaded = (p: ImportPreview) => {
    setPreview(p);
    setStep(1);
  };

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      await apply.mutateAsync(preview.id);
      setApplyTriggered(true);
      setStep(3);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleReset = () => {
    setPreview(null);
    setApplyTriggered(false);
    setStep(0);
  };

  const stepTitles = [t("step1"), t("step2"), t("step3"), t("step4")];
  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "failed" ||
    status.data?.status === "cancelled";

  return (
    <div className="space-y-6" data-testid="import-wizard">
      <Stepper currentStep={step} stepTitles={stepTitles} />

      {step === 0 ? <UploadStep onUploaded={handleUploaded} /> : null}

      {step === 1 && preview ? (
        <PreviewDiff
          preview={preview}
          onBack={handleReset}
          onConfirm={() => setStep(2)}
        />
      ) : null}

      {step === 2 && preview ? (
        <PreviewDiff
          preview={preview}
          onBack={() => setStep(1)}
          onConfirm={handleConfirm}
          isApplying={apply.isPending}
        />
      ) : null}

      {step === 3 && preview ? (
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
