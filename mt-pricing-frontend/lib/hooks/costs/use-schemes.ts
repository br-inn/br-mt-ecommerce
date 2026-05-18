"use client";

import { useQuery } from "@tanstack/react-query";
import { schemesApi, type Scheme, type CostComponentsTemplate } from "@/lib/api/endpoints/schemes";
import { COST_SCHEMES } from "@/lib/api/endpoints/costs";

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------
export const schemeKeys = {
  all: () => ["schemes"] as const,
  list: () => [...schemeKeys.all(), "list"] as const,
  detail: (code: string) => [...schemeKeys.all(), "detail", code] as const,
};

// ---------------------------------------------------------------------------
// Fallback hardcodeado (idéntico al que estaba en _client.tsx).
// Se usa mientras carga o si la API no está disponible.
// ---------------------------------------------------------------------------
const SCHEME_TEMPLATES_FALLBACK: Record<
  (typeof COST_SCHEMES)[number],
  CostComponentsTemplate
> = {
  FBA: {
    required: ["fob_eur", "freight_eur", "customs_aed", "fba_fees_aed"],
    optional: ["payment_fees_pct", "marketing_aed", "storage_aed"],
  },
  FBM: {
    required: ["fob_eur", "freight_eur", "customs_aed", "fbm_fees_aed"],
    optional: ["payment_fees_pct", "marketing_aed"],
  },
  DIRECT_B2C: {
    required: ["fob_eur", "freight_eur", "customs_aed"],
    optional: ["payment_fees_pct", "marketing_aed", "shipping_aed"],
  },
  DIRECT_B2B: {
    required: ["fob_eur", "freight_eur", "customs_aed"],
    optional: ["payment_fees_pct"],
  },
  MARKETPLACE: {
    required: ["fob_eur", "freight_eur", "customs_aed", "marketplace_fees_pct"],
    optional: ["payment_fees_pct", "marketing_aed"],
  },
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Lista todos los schemes activos desde la API.
 * staleTime de 1 hora: los schemes son configuración semestática.
 */
export function useSchemes(enabled = true) {
  return useQuery<Scheme[], Error>({
    queryKey: schemeKeys.list(),
    queryFn: () => schemesApi.list(),
    enabled,
    staleTime: 60 * 60 * 1_000, // 1 hora
    gcTime: 2 * 60 * 60 * 1_000, // 2 horas
  });
}

/**
 * Devuelve el `cost_components_template` para un scheme dado.
 * Si la API aún no respondió o hay error, usa el fallback hardcodeado
 * para no bloquear la UI.
 *
 * @param schemeCode  Código del scheme (FBA, FBM, …)
 */
export function useSchemeTemplate(
  schemeCode: (typeof COST_SCHEMES)[number] | string,
): CostComponentsTemplate {
  const { data: schemes } = useSchemes();

  if (schemes) {
    const match = schemes.find((s) => s.code === schemeCode);
    if (match) {
      return match.cost_components_template;
    }
  }

  // Fallback: devuelve el template hardcodeado mientras carga o si el
  // scheme no está en la respuesta de la API.
  return (
    SCHEME_TEMPLATES_FALLBACK[schemeCode as (typeof COST_SCHEMES)[number]] ?? {
      required: [],
      optional: [],
    }
  );
}

export { SCHEME_TEMPLATES_FALLBACK };
