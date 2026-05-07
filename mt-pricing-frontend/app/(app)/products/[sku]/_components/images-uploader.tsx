"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { useGetUploadUrl } from "@/lib/hooks/products/use-product-images";
import { productKeys } from "@/lib/hooks/products/query-keys";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/avif"];
const MAX_BYTES = 5 * 1024 * 1024; // 5 MB (US-1A-02-06 ADR-033)

interface Props {
  productId: string;
  className?: string;
}

/**
 * Drop zone real para subir imágenes (US-1A-02-04-S2 sub-tarea).
 * Flujo: getUploadUrl → PUT signed URL → invalidate images cache.
 * Backend (Agente 1) genera signed URL y persiste fila product_images.
 */
export function ImagesUploader({ productId, className }: Props) {
  const t = useTranslations("catalog.images");
  const tCommon = useTranslations("common");
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const getUploadUrl = useGetUploadUrl(productId);
  const qc = useQueryClient();

  const validate = (f: File): string | null => {
    if (f.size > MAX_BYTES) return t("errors.tooLarge");
    if (!ACCEPTED_TYPES.includes(f.type)) return t("errors.invalidFormat");
    return null;
  };

  const handleFile = async (file: File) => {
    const err = validate(file);
    if (err) {
      toast.error(err);
      return;
    }
    setBusy(true);
    try {
      const { upload_url } = await getUploadUrl.mutateAsync({
        fileName: file.name,
        contentType: file.type,
      });
      const putRes = await fetch(upload_url, {
        method: "PUT",
        headers: { "Content-Type": file.type },
        body: file,
      });
      if (!putRes.ok) {
        throw new Error(`Upload failed (${putRes.status})`);
      }
      toast.success(t("feedback.uploaded"));
      void qc.invalidateQueries({ queryKey: productKeys.images(productId) });
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : tCommon("error"));
    } finally {
      setBusy(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void handleFile(f);
  };

  const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) void handleFile(f);
    e.target.value = "";
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={t("upload")}
      aria-busy={busy}
      onClick={() => !busy && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (busy) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!busy) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      data-testid="images-uploader"
      className={cn(
        "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center text-sm text-muted-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        dragOver
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/30 bg-muted/30 hover:bg-muted/60",
        busy && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      <UploadCloud className="h-8 w-8" aria-hidden />
      <span className="font-medium text-foreground">{t("upload")}</span>
      <span>{t("uploadHint")}</span>
      <span className="text-xs">{t("limits")}</span>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/avif"
        className="hidden"
        onChange={onSelect}
        disabled={busy}
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="mt-2"
        disabled={busy}
        onClick={(e) => {
          e.stopPropagation();
          inputRef.current?.click();
        }}
      >
        {busy ? tCommon("loading") : t("selectFile")}
      </Button>
    </div>
  );
}
