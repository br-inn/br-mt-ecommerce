"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assetLinksApi } from "@/lib/api/endpoints/asset-links";
import type {
  AssetLink,
  AssetLinkCreatePayload,
  AssetLinkOwnerType,
  AssetLinkWithAsset,
} from "@/lib/api/types-assets-extended";

const assetLinksKeys = {
  all: () => ["asset-links"] as const,
  forOwner: (ownerType: AssetLinkOwnerType, ownerId: string) =>
    [...assetLinksKeys.all(), ownerType, ownerId] as const,
};

export function useAssetLinksForOwner(
  ownerType: AssetLinkOwnerType | undefined,
  ownerId: string | undefined,
) {
  return useQuery<AssetLinkWithAsset[], Error>({
    queryKey: assetLinksKeys.forOwner(
      (ownerType ?? "product") as AssetLinkOwnerType,
      ownerId ?? "",
    ),
    queryFn: () =>
      assetLinksApi.listForOwner(ownerType as AssetLinkOwnerType, ownerId as string),
    enabled: !!ownerType && !!ownerId,
    staleTime: 30_000,
  });
}

export function useCreateAssetLink() {
  const qc = useQueryClient();
  return useMutation<AssetLink, Error, AssetLinkCreatePayload>({
    mutationFn: (payload) => assetLinksApi.create(payload),
    onSettled: (_data, _err, payload) => {
      void qc.invalidateQueries({
        queryKey: assetLinksKeys.forOwner(payload.owner_type, payload.owner_id),
      });
    },
  });
}

export function useDeleteAssetLink() {
  const qc = useQueryClient();
  return useMutation<
    void,
    Error,
    { linkId: string; ownerType: AssetLinkOwnerType; ownerId: string }
  >({
    mutationFn: ({ linkId }) => assetLinksApi.remove(linkId),
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({
        queryKey: assetLinksKeys.forOwner(vars.ownerType, vars.ownerId),
      });
    },
  });
}

export { assetLinksKeys };
