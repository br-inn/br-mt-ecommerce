"use client";

import { useRef, useState } from "react";
import { useImportCatalog, useImportLogistics } from "@/lib/hooks/pricing-desk/use-import";
import type { CatalogImportResult } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
}

type Mode = "catalog" | "logistics";

export function ImportExcelSection({ channelCode }: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>("catalog");
  const [preview, setPreview] = useState<CatalogImportResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const catalogImport = useImportCatalog(channelCode);
  const logisticsImport = useImportLogistics(channelCode);

  const isPending = catalogImport.isPending || logisticsImport.isPending;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    setPreview(null);
  };

  const runPreview = async () => {
    if (!selectedFile) return;
    const fn = mode === "catalog" ? catalogImport : logisticsImport;
    const result = await fn.mutateAsync({ file: selectedFile, confirm: false });
    setPreview(result as CatalogImportResult);
  };

  const confirmImport = async () => {
    if (!selectedFile) return;
    const fn = mode === "catalog" ? catalogImport : logisticsImport;
    await fn.mutateAsync({ file: selectedFile, confirm: true });
    setSelectedFile(null);
    setPreview(null);
    if (fileInput.current) fileInput.current.value = "";
  };

  return (
    <section className="border-b border-mt-border p-3">
      <div className="mt-mono mb-2 text-xs font-semibold uppercase tracking-wider text-mt-ink">
        ⬆ Importar Excel
      </div>

      <div className="mb-2 flex gap-1">
        {(["catalog", "logistics"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => {
              setMode(m);
              setPreview(null);
              setSelectedFile(null);
              if (fileInput.current) fileInput.current.value = "";
            }}
            className={
              "flex-1 rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider transition " +
              (mode === m
                ? "bg-mt-brand text-white"
                : "bg-mt-surface-3 text-mt-ink-2 hover:bg-mt-brand-soft")
            }
          >
            {m === "catalog" ? "Catálogo" : "Logística"}
          </button>
        ))}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept=".xlsx,.xls"
        onChange={handleFileChange}
        className="mb-2 w-full text-xs file:mr-2 file:rounded file:border-0 file:bg-mt-brand file:px-2 file:py-1 file:text-xs file:font-semibold file:text-white hover:file:bg-mt-brand-deep"
      />

      <div className="flex gap-1">
        <button
          type="button"
          onClick={runPreview}
          disabled={!selectedFile || isPending}
          className="flex-1 rounded border border-mt-border bg-white px-2 py-1 text-xs font-semibold text-mt-brand-deep hover:bg-mt-brand-soft disabled:opacity-50"
        >
          {isPending && !preview ? "Procesando…" : "Vista previa"}
        </button>
        <button
          type="button"
          onClick={confirmImport}
          disabled={!preview || isPending}
          className="flex-1 rounded bg-mt-success px-2 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
        >
          Confirmar
        </button>
      </div>

      {preview && (
        <div className="mt-2 rounded border border-mt-border bg-mt-surface-2 p-2 text-[11px]">
          <div className="font-bold text-mt-ink">
            {preview.total_rows} filas — {preview.upserted ?? 0} válidas · {preview.errors.length} errores
          </div>
          {preview.errors.length > 0 && (
            <ul className="mt-1 max-h-32 overflow-auto">
              {preview.errors.slice(0, 5).map((e, i) => (
                <li key={i} className="text-mt-danger">
                  • Fila {(e as { row?: number }).row ?? "?"} ({(e as { sku?: string }).sku}):{" "}
                  {(e as { error?: string }).error}
                </li>
              ))}
              {preview.errors.length > 5 && (
                <li className="text-mt-ink-3">… y {preview.errors.length - 5} más</li>
              )}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
