"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { UploadCloud, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import {
  useConfirmImageUpload,
  useGetUploadUrl,
} from "@/lib/hooks/products/use-product-images";
import type {
  ImageConfirmPayload,
  ProductAsset,
} from "@/lib/api/endpoints/products";

interface Props {
  productId: string;
  /** Si el caller fuerza disabled (RBAC, fila bloqueada, etc.). */
  disabled?: boolean;
  className?: string;
  /** Notifica al padre con la nueva imagen para invalidar caches u optimistic updates. */
  onUploaded?: (img: ProductAsset) => void;
}

const ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp", "image/avif"] as const;
const MAX_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Drag-and-drop uploader. Sprint 2 — wiring completo:
 *   1. Pide signed URL al backend (`POST /products/:sku/images/upload-url`).
 *   2. PUT directo a Supabase Storage via `uploadToSignedUrl(path, token, file)`.
 *   3. Confirma al backend (`POST /products/:sku/images/confirm`) → row creada
 *      + thumbnails dispatch async.
 */
export function ImageUploader({
  productId,
  disabled = false,
  className,
  onUploaded,
}: Props) {
  const t = useTranslations("catalog.images");
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = React.useState(false);
  const [dragOver, setDragOver] = React.useState(false);

  const supabase = React.useMemo(() => createSupabaseBrowserClient(), []);
  const getUploadUrl = useGetUploadUrl(productId);
  const confirmUpload = useConfirmImageUpload(productId);

  const handlePick = () => {
    if (disabled || uploading) return;
    inputRef.current?.click();
  };

  const validateFile = React.useCallback(
    (file: File): string | null => {
      if (!(ALLOWED_MIME as readonly string[]).includes(file.type)) {
        return t("errors.invalidFormat");
      }
      if (file.size > MAX_BYTES) {
        return t("errors.tooLarge");
      }
      return null;
    },
    [t],
  );

  const readDimensions = (file: File): Promise<{ width?: number; height?: number }> =>
    new Promise((resolve) => {
      try {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => {
          resolve({ width: img.naturalWidth, height: img.naturalHeight });
          URL.revokeObjectURL(url);
        };
        img.onerror = () => {
          resolve({});
          URL.revokeObjectURL(url);
        };
        img.src = url;
      } catch {
        resolve({});
      }
    });

  const handleFile = React.useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        toast.error(validationError);
        return;
      }

      setUploading(true);
      try {
        // 1. Pedir signed URL al backend.
        const signed = await getUploadUrl.mutateAsync({
          fileName: file.name,
          contentType: file.type,
        });

        // 2. PUT directo a Supabase Storage.
        const { error: uploadError } = await supabase.storage
          .from(signed.bucket)
          .uploadToSignedUrl(signed.storage_path, signed.token, file);
        if (uploadError) throw uploadError;

        // 3. Leer dimensiones (best-effort, no bloqueante en error).
        const dims = await readDimensions(file);

        // 4. Confirmar al backend.
        // exactOptionalPropertyTypes — solo incluir keys con valor real.
        const confirmPayload: ImageConfirmPayload = {
          storage_path: signed.storage_path,
          mime_type: file.type,
          bytes_size: file.size,
        };
        if (typeof dims.width === "number") confirmPayload.width = dims.width;
        if (typeof dims.height === "number") confirmPayload.height = dims.height;
        const created = await confirmUpload.mutateAsync(confirmPayload);

        toast.success(t("feedback.uploaded"));
        onUploaded?.(created);
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        toast.error(message);
      } finally {
        setUploading(false);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [validateFile, getUploadUrl, supabase, confirmUpload, t, onUploaded],
  );

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled || uploading) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handlePick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handlePick();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled && !uploading) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      aria-disabled={disabled || uploading}
      aria-busy={uploading}
      className={cn(
        "flex w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/30 p-8 text-center text-sm text-muted-foreground transition hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        (disabled || uploading) && "cursor-not-allowed opacity-60 hover:bg-muted/30",
        dragOver && "border-primary bg-primary/5",
        className,
      )}
    >
      {uploading ? (
        <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
      ) : (
        <UploadCloud className="h-8 w-8" aria-hidden />
      )}
      <span className="font-medium">{t("upload")}</span>
      <span>{t("uploadHint")}</span>
      <span className="text-xs text-muted-foreground/80">{t("limits")}</span>
      <input
        ref={inputRef}
        type="file"
        accept={ALLOWED_MIME.join(",")}
        className="hidden"
        disabled={disabled || uploading}
        onChange={handleChange}
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disabled || uploading}
        className="mt-2"
      >
        {uploading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            {t("upload")}
          </>
        ) : (
          t("selectFile")
        )}
      </Button>
    </div>
  );
}
