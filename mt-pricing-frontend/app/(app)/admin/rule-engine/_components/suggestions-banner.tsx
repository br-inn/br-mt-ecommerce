"use client"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import env from "@/lib/env"

interface Suggestion {
  id: string
  suggestion_type: string
  analysis_summary: string | null
  proposed_change: Record<string, unknown>
  status: string
}

export function SuggestionsBanner({
  suggestions,
  onAction,
}: {
  suggestions: Suggestion[]
  onAction: () => void
}) {
  const [loading, setLoading] = useState<string | null>(null)

  if (suggestions.length === 0) return null

  const s = suggestions[0]
  const apiBase = env.NEXT_PUBLIC_BACKEND_URL

  const handleAction = async (action: "apply" | "dismiss") => {
    setLoading(action)
    try {
      const res = await fetch(
        `${apiBase}/api/v1/rule-engine/rule-suggestions/${s.id}/${action}`,
        { method: "POST" }
      )
      if (!res.ok) {
        toast.error("Error al procesar sugerencia")
        return
      }
      toast.success(
        action === "apply"
          ? "Cambio aplicado — aplica a nuevos matches"
          : "Sugerencia descartada"
      )
      onAction()
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="border border-yellow-400 bg-yellow-50 rounded-lg p-4 space-y-3">
      <div className="font-medium text-yellow-800">Sugerencia del Agente IA</div>
      <p className="text-sm text-yellow-700">
        {s.analysis_summary ??
          "El agente detectó una deficiencia en las reglas de esta familia."}
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => handleAction("apply")}
          disabled={loading !== null}
        >
          {loading === "apply" ? "Aplicando..." : "Aplicar cambio sugerido"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => handleAction("dismiss")}
          disabled={loading !== null}
        >
          Descartar
        </Button>
      </div>
    </div>
  )
}
