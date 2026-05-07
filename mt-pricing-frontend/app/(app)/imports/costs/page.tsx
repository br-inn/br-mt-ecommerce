"use client";

import * as React from "react";
import { Check, FileSpreadsheet, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Pill } from "@/components/mt/primitives";
import { cn } from "@/lib/utils/cn";
import {
  useApplyCostsImport,
  useCostsImportStatus,
  useUploadCostsImport,
} from "@/lib/hooks/imports/use-imports-costs";
import type { ImportCostsPreview } from "@/lib/api/endpoints/imports-costs";

const ACCEPTED_MIME = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
];
const MAX_BYTES = 50 * 1024 * 1024;

/**
 * `/imports/costs` — Wizard de importer de costos batch (US-1A-06-02).
 *
 * Reusa el patrón del wizard PIM (`_components/import-wizard.tsx`) pero con
 * shape específico (preview Excel costos → mapping → diff con orphans → apply).
 * Pasos: upload → preview/diff (con sección huérfanos) → apply → report.
 */
export default function ImportsCostsPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Importer de costos
        </h1>
        <p className="text-sm text-muted-foreground">
          Carga batch de costos por SKU × esquema × proveedor con preview y
          reporte de huérfanos.
        </p>
      </header>
      <RbacGuard
        permissions={["imports:write"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
            No tienes permiso para subir costos.
          </div>
        }
      >
        <CostsWizard />
      </RbacGuard>
    </div>
  );
}

type Step = 0 | 1 | 2 | 3;

function CostsWizard() {
  const [step, setStep] = React.useState<Step>(0);
  const [preview, setPreview] = React.useState<ImportCostsPreview | null>(null);
  const upload = useUploadCostsImport();
  const apply = useApplyCostsImport();
  const status = useCostsImportStatus(preview?.run_id, step === 3 && !!preview);

  const handleUploaded = (p: ImportCostsPreview) => {
    setPreview(p);
    setStep(1);
  };

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      await apply.mutateAsync(preview.run_id);
      setStep(3);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al aplicar");
    }
  };

  const handleReset = () => {
    setPreview(null);
    setStep(0);
  };

  const titles = ["Upload", "Diff & huérfanos", "Confirmar", "Resultado"];
  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "completed_with_errors" ||
    status.data?.status === "failed";

  return (
    <div className="space-y-6" data-testid="imports-costs-wizard">
      <Stepper currentStep={step} stepTitles={titles} />

      {step === 0 ? (
        <UploadCard
          isLoading={upload.isPending}
          onUploaded={(p) => handleUploaded(p)}
          onUpload={async (file) => {
            try {
              const r = await upload.mutateAsync({ file });
              handleUploaded(r);
            } catch (err) {
              toast.error(err instanceof Error ? err.message : "Error subiendo archivo");
            }
          }}
        />
      ) : null}

      {step === 1 && preview ? (
        <PreviewSection
          preview={preview}
          onBack={handleReset}
          onConfirm={() => setStep(2)}
        />
      ) : null}

      {step === 2 && preview ? (
        <PreviewSection
          preview={preview}
          onBack={() => setStep(1)}
          onConfirm={handleConfirm}
          confirming={apply.isPending}
        />
      ) : null}

      {step === 3 && preview ? (
        <ResultCard
          run={status.data}
          isTerminal={isTerminal}
          onReset={handleReset}
        />
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
    <ol className="flex items-center gap-2 text-sm" role="list">
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

function UploadCard({
  onUpload,
  isLoading,
}: {
  onUploaded: (p: ImportCostsPreview) => void;
  onUpload: (file: File) => Promise<void>;
  isLoading: boolean;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  const validate = (f: File): string | null => {
    if (f.size > MAX_BYTES) return "El archivo supera 50 MB";
    if (
      !ACCEPTED_MIME.includes(f.type) &&
      !f.name.toLowerCase().endsWith(".xlsx")
    ) {
      return "Formato inválido (sólo .xlsx)";
    }
    return null;
  };

  const pickFile = (f: File) => {
    const err = validate(f);
    if (err) {
      toast.error(err);
      return;
    }
    setFile(f);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sube el archivo de costos</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!file ? (
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const f = e.dataTransfer.files?.[0];
              if (f) pickFile(f);
            }}
            className={cn(
              "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-12 text-center text-sm text-muted-foreground transition",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/30 bg-muted/30 hover:bg-muted/60",
            )}
          >
            <UploadCloud className="h-10 w-10" aria-hidden />
            <span className="font-medium text-foreground">
              Arrastra el .xlsx o haz clic
            </span>
            <span>Hasta 50 MB</span>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) pickFile(f);
                e.target.value = "";
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-md border bg-card p-4">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="h-8 w-8 text-primary" aria-hidden />
              <div className="text-sm">
                <p className="font-medium">{file.name}</p>
                <p className="text-xs text-muted-foreground">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setFile(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        <div className="flex justify-end">
          <Button
            disabled={!file || isLoading}
            onClick={() => file && onUpload(file)}
          >
            {isLoading ? "Procesando…" : "Generar preview"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function PreviewSection({
  preview,
  onBack,
  onConfirm,
  confirming,
}: {
  preview: ImportCostsPreview;
  onBack: () => void;
  onConfirm: () => void;
  confirming?: boolean;
}) {
  const s = preview.summary;
  const orph = preview.orphans;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <SummaryCell label="Total filas" value={s.total} />
        <SummaryCell label="Crear" value={s.create} tone="success" />
        <SummaryCell label="Actualizar" value={s.update} tone="warning" />
        <SummaryCell label="Sin cambio" value={s.no_change} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryCell
          label="SKU no en PIM"
          value={orph.sku_not_in_pim.length}
          tone={orph.sku_not_in_pim.length ? "danger" : "neutral"}
        />
        <SummaryCell
          label="Esquema desconocido"
          value={orph.scheme_unknown.length}
          tone={orph.scheme_unknown.length ? "danger" : "neutral"}
        />
        <SummaryCell
          label="Supplier desconocido"
          value={orph.supplier_unknown.length}
          tone={orph.supplier_unknown.length ? "warning" : "neutral"}
        />
      </div>
      {orph.sku_not_in_pim.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Huérfanos sku_not_in_pim</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-1.5">
              {orph.sku_not_in_pim.slice(0, 50).map((sku) => (
                <Pill key={sku} tone="danger" mono>
                  {sku}
                </Pill>
              ))}
              {orph.sku_not_in_pim.length > 50 ? (
                <Pill tone="ghost">
                  +{orph.sku_not_in_pim.length - 50} más
                </Pill>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}
      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Volver
        </Button>
        <Button onClick={onConfirm} disabled={confirming}>
          {confirming ? "Aplicando…" : "Confirmar y aplicar"}
        </Button>
      </div>
    </div>
  );
}

function SummaryCell({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  return (
    <Card>
      <CardContent className="space-y-1 py-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="text-2xl font-semibold">{value}</p>
        {tone !== "neutral" ? (
          <Pill tone={tone}>{tone}</Pill>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ResultCard({
  run,
  isTerminal,
  onReset,
}: {
  run: import("@/lib/api/endpoints/imports-costs").ImportCostsRun | undefined;
  isTerminal: boolean;
  onReset: () => void;
}) {
  if (!run) {
    return (
      <Card>
        <CardContent className="py-6 text-center text-sm text-muted-foreground">
          Aplicando…
        </CardContent>
      </Card>
    );
  }
  const apply = run.apply;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resultado</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Pill tone={run.status === "completed" ? "success" : "warning"}>
            {run.status}
          </Pill>
        </div>
        {apply ? (
          <div className="grid gap-3 sm:grid-cols-4">
            <SummaryCell label="Created" value={apply.created} tone="success" />
            <SummaryCell label="Updated" value={apply.updated} tone="warning" />
            <SummaryCell label="Errors" value={apply.errors} tone="danger" />
            <SummaryCell
              label="FX missing"
              value={apply.errors_fx_missing}
              tone={apply.errors_fx_missing ? "danger" : "neutral"}
            />
          </div>
        ) : null}
        {isTerminal ? (
          <div className="flex justify-end">
            <Button variant="ghost" onClick={onReset}>
              Subir otro archivo
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
