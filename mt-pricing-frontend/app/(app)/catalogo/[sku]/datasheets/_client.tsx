"use client";

/**
 * Tab "Documentos" del SKU detail (US-1A-06-04 frontend Sprint 4).
 *
 * Pantalla con doble función:
 *  1. Lista de datasheets ya asociados al SKU (preview embebido + descarga
 *     vía signed URL TTL 24h).
 *  2. Wizard inline para subir un nuevo PDF: upload → preview → apply.
 *
 * Flow del wizard:
 *  - Step 0 (default): vista lista + dropzone.
 *  - Step 1: preview con specs extraídas + matched SKUs.
 *  - Step 2: aplicado (refetch listado).
 */

import * as React from "react";
import { Download, ExternalLink, FileText } from "lucide-react";
import { toast } from "sonner";

import {
  MtButton,
  Pill,
  SectionCard,
} from "@/components/mt/primitives";
import {
  MtEmpty,
  MtError,
  MtSkeleton,
} from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { DatasheetsUploader } from "@/components/domain/datasheets/datasheets-uploader";
import { DatasheetsPreview } from "@/components/domain/datasheets/datasheets-preview";
import {
  useApplyDatasheet,
  useDatasheetsForSku,
  useDatasheetsRunStatus,
  useUploadDatasheet,
} from "@/lib/hooks/imports/use-imports-datasheets";
import type {
  DatasheetSummary,
  DatasheetsRun,
} from "@/lib/api/endpoints/imports-datasheets";

interface Props {
  sku: string;
}

const KIND_LABEL = {
  ficha_tecnica: "Ficha técnica",
  compliance: "Compliance",
  manual: "Manual",
} as const;

const KIND_TONE = {
  ficha_tecnica: "brand",
  compliance: "warning",
  manual: "neutral",
} as const;

export function DatasheetsTabClient({ sku }: Props) {
  const list = useDatasheetsForSku(sku);
  const upload = useUploadDatasheet();
  const apply = useApplyDatasheet();
  const [run, setRun] = React.useState<DatasheetsRun | null>(null);
  const [step, setStep] = React.useState<0 | 1 | 2>(0);

  const status = useDatasheetsRunStatus(
    run?.run_id,
    step === 2 && !!run,
  );

  const isTerminal =
    status.data?.status === "completed" ||
    status.data?.status === "completed_with_errors" ||
    status.data?.status === "failed";

  const handleUpload = async (file: File) => {
    try {
      const r = await upload.mutateAsync({ file, sku });
      setRun(r);
      setStep(1);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error subiendo PDF");
    }
  };

  const handleApply = async () => {
    if (!run) return;
    try {
      const r = await apply.mutateAsync(run.run_id);
      setRun(r);
      setStep(2);
      toast.success("Datasheet aplicado");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error aplicando");
    }
  };

  const handleReset = () => {
    setRun(null);
    setStep(0);
    void list.refetch();
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="Datasheets asociados"
        subtitle="Fichas técnicas, compliance y manuales del SKU"
        actions={
          list.data ? (
            <Pill tone="brand" mono>
              {list.data.length}
            </Pill>
          ) : null
        }
      >
        <DatasheetsList query={list} />
      </SectionCard>

      <SectionCard
        title="Subir nuevo datasheet"
        subtitle="PDF con naming convention MTFT_/MTCE_/MTMAN_*"
      >
        <div className="px-4 py-4">
          {step === 0 ? (
            <DatasheetsUploader
              onUpload={handleUpload}
              isLoading={upload.isPending}
              sku={sku}
            />
          ) : null}

          {step === 1 && run ? (
            <DatasheetsPreview
              run={run}
              applying={apply.isPending}
              onApply={handleApply}
              onBack={handleReset}
            />
          ) : null}

          {step === 2 ? (
            <div className="space-y-3">
              <ApplyResult
                run={status.data ?? run}
                isTerminal={isTerminal}
              />
              <div className="flex justify-end">
                <MtButton tone="ghost" onClick={handleReset}>
                  Subir otro PDF
                </MtButton>
              </div>
            </div>
          ) : null}
        </div>
      </SectionCard>
    </div>
  );
}

function DatasheetsList({
  query,
}: {
  query: ReturnType<typeof useDatasheetsForSku>;
}) {
  if (query.isLoading) {
    return (
      <div className="space-y-2 p-4">
        <MtSkeleton width="100%" height={48} />
        <MtSkeleton width="100%" height={48} />
      </div>
    );
  }
  if (query.isError) {
    return (
      <div className="p-4">
        <MtError
          message="No se pudieron cargar los datasheets."
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  }
  const items = query.data ?? [];
  if (items.length === 0) {
    return (
      <MtEmpty
        title="Sin datasheets"
        hint="Sube un PDF en la sección inferior para asociar fichas a este SKU."
        icon={<FileText className="size-6" strokeWidth={1.4} />}
      />
    );
  }
  return (
    <ul className="divide-y" style={{ borderColor: MT.border }}>
      {items.map((d) => (
        <li key={d.id} className="px-4 py-3">
          <DatasheetItem datasheet={d} />
        </li>
      ))}
    </ul>
  );
}

function DatasheetItem({ datasheet }: { datasheet: DatasheetSummary }) {
  const kindLabel = KIND_LABEL[datasheet.kind];
  const kindTone = KIND_TONE[datasheet.kind];
  return (
    <div className="flex flex-wrap items-center gap-3">
      <FileText className="size-5" style={{ color: MT.brand }} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
          <span className="mt-mono font-medium truncate" style={{ color: MT.ink }}>
            {datasheet.original_filename}
          </span>
          <Pill tone={kindTone}>{kindLabel}</Pill>
        </div>
        <div
          className="mt-1 flex flex-wrap items-center gap-2 text-[11.5px]"
          style={{ color: MT.ink3 }}
        >
          <span>{(datasheet.file_size_bytes / 1024).toFixed(0)} KB</span>
          {datasheet.page_count !== null ? (
            <span>· {datasheet.page_count} páginas</span>
          ) : null}
          <span>
            · subido {new Date(datasheet.uploaded_at).toLocaleDateString()}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <MtButton
          tone="neutral"
          size="sm"
          asChild
          icon={<ExternalLink className="size-3.5" />}
        >
          <a
            href={datasheet.signed_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ver
          </a>
        </MtButton>
        <MtButton
          tone="primary"
          size="sm"
          asChild
          icon={<Download className="size-3.5" />}
        >
          <a href={datasheet.signed_url} download={datasheet.original_filename}>
            Descargar
          </a>
        </MtButton>
      </div>
    </div>
  );
}

function ApplyResult({
  run,
  isTerminal,
}: {
  run: DatasheetsRun | null | undefined;
  isTerminal: boolean;
}) {
  if (!run) {
    return (
      <div className="text-[12.5px]" style={{ color: MT.ink3 }}>
        Esperando…
      </div>
    );
  }
  const statusTone =
    run.status === "completed"
      ? "success"
      : run.status === "completed_with_errors"
        ? "warning"
        : run.status === "failed"
          ? "danger"
          : "neutral";
  return (
    <div className="space-y-2 text-[12.5px]">
      <div className="flex items-center gap-2">
        <Pill tone={statusTone} dot>
          {run.status}
        </Pill>
        {!isTerminal ? (
          <span style={{ color: MT.ink3 }}>Aplicando…</span>
        ) : null}
      </div>
      {run.applied ? (
        <div style={{ color: MT.ink3 }}>
          Persistidos: <strong style={{ color: MT.ink }}>{run.applied.persisted}</strong>{" "}
          · errores:{" "}
          <strong
            style={{
              color: run.applied.errors > 0 ? MT.danger : MT.ink,
            }}
          >
            {run.applied.errors}
          </strong>
        </div>
      ) : null}
      {run.error ? (
        <div className="text-[12.5px]" style={{ color: MT.danger }}>
          Error: {run.error}
        </div>
      ) : null}
    </div>
  );
}

export default DatasheetsTabClient;
