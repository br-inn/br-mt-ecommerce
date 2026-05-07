"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ImageGallery } from "@/components/domain/image-gallery";
import { ImageUploader } from "@/components/domain/image-uploader";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { useProduct } from "@/lib/hooks/products/use-product";

export function ImagesTab({ sku }: { sku: string }) {
  const { data: product, isLoading } = useProduct(sku);

  if (isLoading) {
    return <Skeleton className="h-64 w-full rounded-lg" />;
  }
  if (!product) return null;

  return (
    <div className="space-y-6">
      <ImageGallery productId={product.id} />
      <RbacGuard permissions={["products:write"]}>
        <ImageUploader productId={product.id} />
      </RbacGuard>
    </div>
  );
}
