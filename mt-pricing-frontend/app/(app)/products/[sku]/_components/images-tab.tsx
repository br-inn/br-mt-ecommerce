"use client";

import { useTranslations } from "next-intl";

import { ImageGallery } from "@/components/domain/image-gallery";
import { RbacGuard } from "@/components/auth/rbac-guard";
import type { ProductAsset } from "@/lib/api/endpoints/products";
import { ImagesUploader } from "./images-uploader";

interface Props {
  productId: string;
  images: ProductAsset[];
}

/**
 * Tab "Imágenes" del detalle de SKU (US-1A-02-04-S2).
 * - Drop zone real (`ImagesUploader`) para usuarios con `products:write`.
 * - Galería (`ImageGallery` ya existente) con set-primary + delete.
 */
export function ImagesTab({ productId, images }: Props) {
  const t = useTranslations("catalog.images");

  return (
    <div className="space-y-4" data-testid="product-images-tab">
      <header className="space-y-1">
        <h2 className="text-lg font-semibold">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </header>

      <RbacGuard permissions={["products:write"]}>
        <ImagesUploader productId={productId} />
      </RbacGuard>

      <ImageGallery productId={productId} images={images} />
    </div>
  );
}
