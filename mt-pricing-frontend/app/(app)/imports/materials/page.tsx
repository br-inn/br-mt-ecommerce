"use client";

import * as React from "react";
import { Check, FileSpreadsheet, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Pill } from "@/components/mt/primitives";
import { cn } from "@/lib/utils/cn";
import {
  useApplyMaterialsImport,
  useMaterialsImportStatus,
  useUploadMaterialsImport,
} from "@/lib/hooks/imports/use-imports-materials";
import type {
  ImportMaterialsApplyMode,
  ImportMaterialsPreview,
} from "@/lib/api/endpoints/imports-materials";

const MAX_BYTES = 50 * 1024 * 1024;

/**
 * `/imports/materials` — Wizard de importer de compatibilidades materiales
 * (US-1A-06-03). Reusa el patrón del wizard PIM/costs adaptando el shape
 * (preview Excel materiales → diff implícito → apply replace/append).
 */
export default function ImportsMaterialsPage() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          Importer de compatibilidades materiales
        </h1>
        <p className="text-sm text-muted-foreground">
          Carga la matriz materiales × T °C (idempotente: modo replace trunca y
          recarga).
        </p>
      </header>
      <RbacGuard
        permissions={["imports:write"]}
        fallback={
          <div className="rounded-md border border-amber-500/30 bg-amber-50 p-4 text-sm text-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
            No tienes permiso.
          </div>
        }
      >
        <MaterialsWizard />
      </RbacGuard>
    </div>
  );
}

type Step = 0 | 1 | 2;

function MaterialsWizard() {
  const [step, setStep] = React.useState<Step>(0);
  const [preview, setPreview] = React.useState<ImportMaterialsPreview | null>(
    null,
  );
  const [mode, setMode] = React.useState<ImportMaterialsApplyMode>("replace");
  const upload = useUploadMaterialsImport();
  const apply = useApplyMaterialsImport();
  const status = useMaterialsImportStatus(
    preview?.run_id,
    step === 2 && !!preview,
  );

  const handleConfirm = async () => {
    if (!preview) return;
    try {
      await apply.mutateAsync({ runId: preview.run_id, mode });
      setStep(2);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error al aplicar");
    }
  };

  const titles = ["Upload", "Preview", "Resultado"];
  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "completed_with_errors" ||
    status.data?.status === "failed";

  return (
    <div className="space-y-6" data-testid="imports-materials-wizard">
      <Stepper currentStep={step} stepTitles={titles} />

      {step === 0 ? (
        <UploadCard
          isLoading={upload.isPending}
          onUpload={async (file) => {
            try {
              const r = await upload.mutateAsync({ file });
              setPreview(r);
              setStep(1);
            } catch (err) {
              toast.error(err instanceof Error ? err.message : "Error subiendo");
            }
          }}
        />
      ) : null}

      {step === 1 && preview ? (
        <PreviewSection
          preview={preview}
          mode={mode}
          onModeChange={setMode}
          onBack={() => {
            setPreview(null);
            setStep(0);
          }}
          onConfirm={handleConfirm}
          confirming={apply.isPending}
        />
      ) : null}

      {step === 2 ? (
        <ResultCard
          run={status.data}
          isTerminal={isTerminal}
          onReset={() => {
            setPreview(null);
            setStep(0);
          }}
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
    <ol className="flex items-center gap-2 text-sm">
      {stepTitles.map((title, idx) => {
        const done = idx < currentStep;
        const current = idx === currentStep;
        return (
          <li key={title} className="flex flex-1 items-center gap-2">
            <span
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
              <span className="h-px flex-1 bg-border" />
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
  onUpload: (file: File) => Promise<void>;
  isLoading: boolean;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sube el .xlsx de compatibilidades</CardTitle>
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
              if (f) {
                if (f.size > MAX_BYTES) {
                  toast.error("Archivo > 50 MB");
                  return;
                }
                setFile(f);
              }
            }}
            className={cn(
              "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-12 text-center text-sm text-muted-foreground transition",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/30 bg-muted/30 hover:bg-muted/60",
            )}
          >
            <UploadCloud className="h-10 w-10" />
            <span className="font-medium text-foreground">
              Arrastra el .xlsx o haz clic
            </span>
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) {
                  if (f.size > MAX_BYTES) {
                    toast.error("Archivo > 50 MB");
                    return;
                  }
                  setFile(f);
                }
                e.target.value = "";
              }}
            />
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-md border bg-card p-4">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="h-8 w-8 text-primary" />
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
            onClick={() => file && onUpload(file)}
            disabled={!file || isLoading}
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
  mode,
  onModeChange,
  onBack,
  onConfirm,
  confirming,
}: {
  preview: ImportMaterialsPreview;
  mode: ImportMaterialsApplyMode;
  onModeChange: (m: ImportMaterialsApplyMode) => void;
  onBack: () => void;
  onConfirm: () => void;
  confirming?: boolean;
}) {
  const s = preview.summary;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <SummaryCell label="Total filas" value={s.total} />
        <SummaryCell label="OK" value={s.ok} tone="success" />
        <SummaryCell label="Errores" value={s.errors} tone={s.errors ? "danger" : "neutral"} />
        <SummaryCell label="Materiales" value={s.materials_columns} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Modo de aplicación</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-3">
          <Select
            value={mode}
            onValueChange={(v) => onModeChange(v as ImportMaterialsApplyMode)}
          >
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="replace">Replace (TRUNCATE+INSERT)</SelectItem>
              <SelectItem value="append">Append</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-xs text-muted-foreground">
            {mode === "replace"
              ? "Trunca la tabla y recarga las filas (idempotente)."
              : "Sólo inserta. Útil para diffs futuros."}
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Materiales detectados</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-1.5">
          {preview.materials_columns.slice(0, 50).map((m) => (
            <Pill key={m} tone="brand" mono>
              {m}
            </Pill>
          ))}
        </CardContent>
      </Card>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onBack}>
          Volver
        </Button>
        <Button onClick={onConfirm} disabled={confirming}>
          {confirming ? "Aplicando…" : "Aplicar"}
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
        {tone !== "neutral" ? <Pill tone={tone}>{tone}</Pill> : null}
      </CardContent>
    </Card>
  );
}

function ResultCard({
  run,
  isTerminal,
  onReset,
}: {
  run: import("@/lib/api/endpoints/imports-materials").ImportMaterialsRun | undefined;
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
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resultado</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Pill tone={run.status === "completed" ? "success" : "warning"}>
          {run.status}
        </Pill>
        {run.apply ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryCell
              label="Inserted"
              value={run.apply.inserted}
              tone="success"
            />
            <SummaryCell
              label="Truncado"
              value={run.apply.truncated ? 1 : 0}
              tone={run.apply.truncated ? "warning" : "neutral"}
            />
            <SummaryCell
              label="Errors"
              value={run.apply.errors}
              tone={run.apply.errors ? "danger" : "neutral"}
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
