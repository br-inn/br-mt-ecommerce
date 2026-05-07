"use client";

import * as React from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { toast } from "sonner";

import { MtButton } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";

interface Props {
  onUpload: (file: File) => Promise<void>;
  isLoading: boolean;
  /** Si se conoce el SKU contexto, lo mostramos como hint. */
  sku?: string | undefined;
  /** Tamaño máximo en bytes (default 10 MB per US-1A-06-04 AC#5). */
  maxBytes?: number | undefined;
}

const ACCEPTED_MIME = ["application/pdf"];
const ACCEPTED_EXT = [".pdf"];

/**
 * Drop-zone para subir un PDF de datasheet (`MTFT_*` / `MTCE_*` / `MTMAN_*`).
 *
 * UX:
 *  - Drag-and-drop + click para seleccionar.
 *  - Valida MIME + tamaño (default 10 MB).
 *  - Una vez seleccionado, muestra preview con metadata y botón "Generar
 *    preview" → llama `onUpload`.
 */
export function DatasheetsUploader({
  onUpload,
  isLoading,
  sku,
  maxBytes = 10 * 1024 * 1024,
}: Props) {
  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const validate = (f: File): string | null => {
    if (f.size > maxBytes) return `El archivo supera ${(maxBytes / 1024 / 1024).toFixed(0)} MB`;
    const mimeOk = ACCEPTED_MIME.includes(f.type);
    const extOk = ACCEPTED_EXT.some((ext) =>
      f.name.toLowerCase().endsWith(ext),
    );
    if (!mimeOk && !extOk) return "Sólo se permiten PDFs";
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

  const handleSubmit = async () => {
    if (!file) return;
    try {
      await onUpload(file);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Error subiendo PDF");
    }
  };

  return (
    <div className="space-y-3">
      {sku ? (
        <div
          className="rounded-md border px-3 py-2 text-[12.5px]"
          style={{
            borderColor: MT.brandBorder,
            backgroundColor: MT.brandSofter,
            color: MT.ink2,
          }}
        >
          SKU contexto: <span className="mt-mono">{sku}</span>. Se asociará
          automáticamente si el filename matchea el sufijo numérico.
        </div>
      ) : null}

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
          className="flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-10 text-center text-[12.5px]"
          style={{
            borderColor: dragOver ? MT.brand : MT.borderStrong,
            backgroundColor: dragOver ? MT.brandSofter : MT.surface2,
            color: MT.ink3,
          }}
          data-testid="datasheets-dropzone"
        >
          <UploadCloud className="size-8" aria-hidden style={{ color: MT.ink4 }} />
          <span className="font-medium" style={{ color: MT.ink }}>
            Arrastra el PDF o haz clic para seleccionar
          </span>
          <span>
            Naming convention: <code className="mt-mono">MTFT_5114.pdf</code>,{" "}
            <code className="mt-mono">MTCE_5114.pdf</code>,{" "}
            <code className="mt-mono">MTMAN_5114.pdf</code>
          </span>
          <span style={{ color: MT.ink4 }}>
            Máximo {(maxBytes / 1024 / 1024).toFixed(0)} MB
          </span>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) pickFile(f);
              e.target.value = "";
            }}
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-between rounded-md border p-3"
          style={{ borderColor: MT.border, backgroundColor: MT.surface }}
        >
          <div className="flex items-center gap-3">
            <FileText className="size-7" style={{ color: MT.brand }} />
            <div className="text-[12.5px]">
              <p className="font-medium" style={{ color: MT.ink }}>
                {file.name}
              </p>
              <p style={{ color: MT.ink3 }}>
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <MtButton
            tone="ghost"
            size="sm"
            onClick={() => setFile(null)}
            icon={<X className="size-3.5" />}
            aria-label="Quitar archivo"
          />
        </div>
      )}

      <div className="flex justify-end">
        <MtButton
          tone="primary"
          disabled={!file || isLoading}
          onClick={handleSubmit}
          data-testid="datasheets-submit-preview"
        >
          {isLoading ? "Procesando…" : "Generar preview"}
        </MtButton>
      </div>
    </div>
  );
}
