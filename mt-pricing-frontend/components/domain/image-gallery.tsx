"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Star, Trash2, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { cn } from "@/lib/utils/cn";
import {
  useDeleteImage,
  useProductImages,
  useSetPrimaryImage,
} from "@/lib/hooks/products/use-product-images";

interface Props {
  productId: string;
  className?: string;
}

export function ImageGallery({ productId, className }: Props) {
  const t = useTranslations("catalog.images");
  const tCommon = useTranslations("common");
  const { data, isLoading, isError, refetch } = useProductImages(productId);
  const setPrimary = useSetPrimaryImage(productId);
  const deleteImage = useDeleteImage(productId);
  const [confirmId, setConfirmId] = React.useState<string | null>(null);

  if (isLoading) {
    return (
      <div className={cn("grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4", className)}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        <p>{tCommon("error")}</p>
        <Button variant="link" onClick={() => refetch()}>
          {tCommon("retry")}
        </Button>
      </div>
    );
  }

  const images = data ?? [];

  if (images.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground">
        <ImageIcon className="h-10 w-10" aria-hidden />
        <p>{t("noImages")}</p>
      </div>
    );
  }

  const handleSetPrimary = async (imageId: string) => {
    try {
      await setPrimary.mutateAsync(imageId);
      toast.success(t("feedback.primarySet"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const handleDelete = async () => {
    if (!confirmId) return;
    try {
      await deleteImage.mutateAsync(confirmId);
      toast.success(t("feedback.deleted"));
      setConfirmId(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  return (
    <>
      <ul
        className={cn("grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4", className)}
        aria-label={t("title")}
      >
        {images.map((img) => (
          <li
            key={img.id}
            className="group relative overflow-hidden rounded-lg border bg-muted"
          >
            <div className="relative aspect-square w-full">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={
                  img.urls.thumb_400 ??
                  img.urls.original ??
                  img.original_url ??
                  ""
                }
                alt={img.alt_text ?? ""}
                className="h-full w-full object-cover"
                loading="lazy"
              />
              {img.is_primary ? (
                <Badge className="absolute left-2 top-2 gap-1 bg-amber-400 text-amber-950 hover:bg-amber-400">
                  <Star className="h-3 w-3 fill-current" aria-hidden />
                  {t("primary")}
                </Badge>
              ) : null}
            </div>
            <div className="flex items-center justify-between gap-2 p-2">
              <RbacGuard permissions={["products:write"]}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSetPrimary(img.id)}
                  disabled={img.is_primary || setPrimary.isPending}
                  aria-label={t("setPrimary")}
                >
                  <Star className="h-3 w-3" aria-hidden />
                  <span className="sr-only sm:not-sr-only">{t("setPrimary")}</span>
                </Button>
              </RbacGuard>
              <RbacGuard permissions={["products:write"]}>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={() => setConfirmId(img.id)}
                  aria-label={t("delete")}
                >
                  <Trash2 className="h-3 w-3" aria-hidden />
                </Button>
              </RbacGuard>
            </div>
          </li>
        ))}
      </ul>

      <Dialog open={!!confirmId} onOpenChange={(open) => !open && setConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("delete")}</DialogTitle>
            <DialogDescription>{t("deleteConfirm")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmId(null)}>
              {tCommon("cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteImage.isPending}
            >
              {tCommon("delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
