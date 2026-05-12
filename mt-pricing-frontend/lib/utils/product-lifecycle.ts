export type ProductLifecycleStatus =
  | "draft"
  | "active"
  | "deprecated"
  | "replaced"
  | "discontinued";

/**
 * Derives the legacy `active` flag from `lifecycle_status`.
 * Use this for new code; existing uses of `product.active` stay intact
 * (full migration is Phase B).
 */
export const isProductActive = (
  product: { lifecycle_status?: string | null },
): boolean => product.lifecycle_status === "active";
