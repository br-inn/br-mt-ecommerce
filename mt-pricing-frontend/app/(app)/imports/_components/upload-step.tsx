"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { UploadCloud, FileSpreadsheet, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useUploadImport } from "@/lib/hooks/imports/use-imports";
import type { ImportPreview } from "@/lib/api/endpoints/imports";

const ACCEPTED = [
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
];
const MAX_BYTES = 50 * 1024 * 1024; // 50 MB (NFR importer)

interface Props {
  onUploaded: (preview: ImportPreview) => void;
}

/** Step 1: drop zone + upload. */
export function UploadStep({ onUploaded }: Props) {
  const t = useTranslations("imports.upload");
  const tCommon = useTranslations("common");
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const upload = useUploadImport();

  const validate = (f: File): string | null => {
    if (f.size > MAX_BYTES) return t("errors.tooLarge");
    if (
      !ACCEPTED.includes(f.type) &&
      !f.name.toLowerCase().endsWith(".xlsx") &&
      !f.name.toLowerCase().endsWith(".xls")
    ) {
      return t("errors.invalidFormat");
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

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) pickFile(f);
  };

  const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) pickFile(f);
    e.target.value = "";
  };

  const handleSubmit = async () => {
    if (!file) return;
    try {
      const preview = await upload.mutateAsync({ file });
      onUploaded(preview);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  return (
    <div className="space-y-4" data-testid="import-upload-step">
      {!file ? (
        <div
          role="button"
          tabIndex={0}
          aria-label={t("dropLabel")}
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
          onDrop={onDrop}
          data-testid="import-dropzone"
          className={cn(
            "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-12 text-center text-sm text-muted-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/30 bg-muted/30 hover:bg-muted/60",
          )}
        >
          <UploadCloud className="h-10 w-10" aria-hidden />
          <span className="font-medium text-foreground">{t("title")}</span>
          <span>{t("hint")}</span>
          <span className="text-xs">{t("limits")}</span>
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={onSelect}
            data-testid="import-file-input"
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-between rounded-md border bg-card p-4"
          data-testid="import-file-preview"
        >
          <div className="flex items-center gap-3">
            <FileSpreadsheet className="h-8 w-8 text-primary" aria-hidden />
            <div className="text-sm">
              <p className="font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setFile(null)}
            aria-label={t("remove")}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleSubmit}
          disabled={!file || upload.isPending}
          data-testid="import-upload-submit"
        >
          {upload.isPending ? t("uploading") : t("startPreview")}
        </Button>
      </div>
    </div>
  );
}
