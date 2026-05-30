/**
 * Estado de vigencia de un coste derivado por FECHA respecto a hoy.
 *
 * Módulo SIN `"use client"` a propósito: contiene únicamente lógica pura
 * (sin JSX ni componentes) para que pueda importarse tanto desde
 * `cost-table.tsx` como desde `cost-timeline.tsx` sin que el transform de
 * React Fast Refresh (que sólo conserva exports de componentes en módulos
 * cliente) elimine el helper.
 *
 * Contrato de vigencia por rangos:
 *   Vigente    → hoy ∈ [valid_from, valid_to]  (o valid_to null & valid_from ≤ hoy)
 *   Programado → valid_from > hoy
 *   Caducado   → valid_to < hoy
 *
 * Las comparaciones son lexicográficas sobre "YYYY-MM-DD" (ISO date).
 */

export type CostState = "vigente" | "programado" | "caducado";

/** Hoy en formato "YYYY-MM-DD" (local), comparable lexicográficamente con dates ISO. */
export function todayIso(): string {
  return new Date().toLocaleDateString("en-CA"); // en-CA → "YYYY-MM-DD"
}

/** Estado del coste derivado por fecha respecto a hoy. */
export function costState(cost: {
  valid_from: string;
  valid_to: string | null;
}): CostState {
  const today = todayIso();
  if (cost.valid_from > today) return "programado";
  if (cost.valid_to && cost.valid_to < today) return "caducado";
  return "vigente";
}
