"use client";

/**
 * Mutaciones aisladas — re-exports de `use-costs.ts` con nombres
 * ligeramente más descriptivos para la UI Costes (US-1A-04-04).
 *
 * Convención: cada componente que mute costs importa de aquí, NO de
 * `use-costs.ts` directamente, para que la separación reads/mutations sea
 * visible en imports.
 */

export {
  useCreateCost,
  useDeleteCost,
  usePatchCost,
  useUpdateCost,
} from "./use-costs";
