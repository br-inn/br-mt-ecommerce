"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"
import env from "@/lib/env"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

interface Suggestion {
  id: string
  suggestion_type: string
  analysis_summary: string | null
  proposed_change: Record<string, unknown>
  status: string
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

export function SuggestionsBanner({
  suggestions,
}: {
  suggestions: Suggestion[]
}) {
  const router = useRouter()
  const [loading, setLoading] = useState<string | null>(null)

  if (suggestions.length === 0) return null

  const s = suggestions[0]!

  const handleAction = async (action: "apply" | "dismiss") => {
    setLoading(action)
    try {
      const authHeader = await getAuthHeader()
      const res = await fetch(
        `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/rule-suggestions/${s.id}/${action}`,
        { method: "POST", headers: authHeader }
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
      router.refresh()
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
