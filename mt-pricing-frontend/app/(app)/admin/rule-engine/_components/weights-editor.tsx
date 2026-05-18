"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"
import env from "@/lib/env"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

const DIMENSION_LABELS: Record<string, string> = {
  material: "Material",
  pn: "Presión nominal (PN)",
  dn: "Diámetro nominal (DN)",
  product_type: "Tipo de producto",
  thread_standard: "Estándar de rosca",
  ways: "Número de vías",
  norma: "Norma",
  brand_tier: "Tier de marca",
  delivery: "Entrega",
  data_completeness: "Completitud de datos",
  actuator: "Tipo de actuador",
}

// Catálogo de blockers conocidos — aparecen siempre como opciones aunque no estén en el perfil
const KNOWN_BLOCKERS: string[] = [
  "dn_mismatch",
  "material_mismatch",
  "product_type_mismatch",
  "ways_mismatch",
  "pn_below_sku_requirement",
  "pn_too_far_above",
  "mini_mismatch",
  "thread_mismatch",
  "handle_mismatch",
  "actuator_mismatch",
  "connection_gender_mismatch",
  "bore_type_mismatch",
  "seat_material_mismatch",
  "seal_material_mismatch",
]

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

function extractErrorMessage(err: unknown, fallback: string): string {
  if (!err || typeof err !== "object") return fallback
  const detail = (err as Record<string, unknown>).detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object") {
    const title = (detail as Record<string, unknown>).title
    if (typeof title === "string") return title
  }
  return fallback
}

interface WeightsEditorProps {
  family: string
  initialWeights: Record<string, number>
  initialBlockers: string[]
}

export function WeightsEditor({ family, initialWeights, initialBlockers }: WeightsEditorProps) {
  const [weights, setWeights] = useState(initialWeights)
  const [blockers, setBlockers] = useState<Set<string>>(new Set(initialBlockers))
  const [saving, setSaving] = useState(false)

  const total = Object.values(weights).reduce((a, b) => a + b, 0)
  const sumOk = Math.abs(total - 1.0) < 0.001

  const handleSave = async () => {
    setSaving(true)
    try {
      const authHeader = await getAuthHeader()
      const res = await fetch(
        `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/taxonomy-profiles/${encodeURIComponent(family)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeader },
          body: JSON.stringify({ weights, hard_blockers: Array.from(blockers) }),
        }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        toast.error(extractErrorMessage(err, "Error al guardar"))
        return
      }
      toast.success("Regla guardada — aplica a nuevos matches")
    } finally {
      setSaving(false)
    }
  }

  const toggleBlocker = (blocker: string) => {
    setBlockers(prev => {
      const next = new Set(prev)
      if (next.has(blocker)) next.delete(blocker)
      else next.add(blocker)
      return next
    })
  }

  const allBlockers = Array.from(new Set([...KNOWN_BLOCKERS, ...initialBlockers, ...Array.from(blockers)]))

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="font-medium">Pesos por dimensión</h2>
          <Badge variant={sumOk ? "outline" : "destructive"}>
            Suma: {total.toFixed(3)} {sumOk ? "✓" : "≠ 1.000"}
          </Badge>
        </div>
        {Object.entries(weights).map(([dim, val]) => (
          <div key={dim} className="grid grid-cols-[160px_1fr_60px] gap-4 items-center">
            <span className="text-sm">{DIMENSION_LABELS[dim] ?? dim}</span>
            <input
              type="range"
              min={0}
              max={0.5}
              step={0.01}
              value={val}
              onChange={(e) =>
                setWeights(prev => ({ ...prev, [dim]: parseFloat(e.target.value) }))
              }
              className="w-full"
            />
            <span className="text-sm text-right font-mono">{val.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <h2 className="font-medium">Hard Blockers</h2>
        <p className="text-sm text-muted-foreground">
          Condiciones que descartan automáticamente un candidato.
        </p>
        {allBlockers.map(b => (
          <label key={b} className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={blockers.has(b)}
              onChange={() => toggleBlocker(b)}
              className="rounded"
            />
            <span className="font-mono">{b}</span>
          </label>
        ))}
      </div>
      <Button onClick={handleSave} disabled={!sumOk || saving}>
        {saving ? "Guardando..." : "Guardar cambios"}
      </Button>
    </div>
  )
}
