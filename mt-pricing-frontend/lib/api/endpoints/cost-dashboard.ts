"use client";

import { COST_SCHEMES, costsApi, type CostMissingItem, type CostScheme } from "@/lib/api/endpoints/costs";

/**
 * Cost dashboard helpers (US-1A-DEV-01 frontend / S5).
 *
 * Reutiliza `/api/v1/costs/missing` (S3 live) y `/api/v1/products` para
 * agregar cobertura por scheme. El backend NO expone aún un endpoint
 * "overview" — calculamos los KPIs en cliente con N requests paralelos
 * (uno por scheme; máximo 5 por COST_SCHEMES).
 */

export interface SchemeCoverage {
  scheme: CostScheme;
  missing: CostMissingItem[];
  /** Coste total de SKUs con coste activo por este scheme (calculado client-side). */
  missingCount: number;
}

export interface CostDashboardOverview {
  totalProducts: number;
  schemes: SchemeCoverage[];
  computedAt: string;
}

export const costDashboardApi = {
  /** Lanza N=COST_SCHEMES.length requests paralelos a `/costs/missing?scheme_code=`. */
  overview: async (totalProducts: number): Promise<CostDashboardOverview> => {
    const results = await Promise.all(
      COST_SCHEMES.map(async (scheme) => {
        const missing = await costsApi.missingForScheme(scheme);
        return {
          scheme,
          missing,
          missingCount: missing.length,
        } satisfies SchemeCoverage;
      }),
    );
    return {
      totalProducts,
      schemes: results,
      computedAt: new Date().toISOString(),
    };
  },
};
