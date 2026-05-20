"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ImageGallery } from "@/components/domain/image-gallery";
import { ImageUploader } from "@/components/domain/image-uploader";
import { AssetGalleryPolymorphic } from "@/components/domain/asset-gallery-polymorphic";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { MtError } from "@/components/mt/states";
import { useProduct } from "@/lib/hooks/products/use-product";

export function ImagesTab({ sku }: { sku: string }) {
  const { data: product, isLoading, isError, refetch } = useProduct(sku);

  if (isLoading) {
    return <Skeleton className="h-64 w-full rounded-lg" />;
  }
  if (isError || !product) {
    return (
      <MtError
        message="No se pudo cargar la información del producto."
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="space-y-8">
      <ImageGallery productId={product.id} />
      <RbacGuard permissions={["products:write"]}>
        <ImageUploader productId={product.id} />
      </RbacGuard>

      <section className="space-y-2">
        <h3 className="text-base font-semibold">All assets (polymorphic)</h3>
        <p className="text-sm text-muted-foreground">
          Vista unificada de assets vinculados al producto vía asset_links
          (imágenes, PDFs, videos, planos).
        </p>
        <AssetGalleryPolymorphic ownerType="product" ownerId={sku} />
      </section>
    </div>
  );
}
