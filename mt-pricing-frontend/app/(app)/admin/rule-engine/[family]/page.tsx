import { notFound } from "next/navigation"
import { WeightsEditor } from "../_components/weights-editor"
import { SuggestionsBanner } from "../_components/suggestions-banner"
import env from "@/lib/env"
import { createClient } from "@/lib/supabase/server"

const apiBase = process.env.BACKEND_URL ?? env.NEXT_PUBLIC_BACKEND_URL

async function authHeaders(): Promise<HeadersInit> {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

async function getProfile(family: string, headers: HeadersInit) {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/taxonomy-profiles/${encodeURIComponent(family)}`,
    { cache: "no-store", headers }
  )
  if (res.status === 404) return null
  if (!res.ok) throw new Error("Error cargando perfil")
  return res.json()
}

async function getPendingSuggestions(profileId: string, headers: HeadersInit) {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/rule-suggestions?status=pending`,
    { cache: "no-store", headers }
  )
  if (!res.ok) return []
  const all: Array<{
    taxonomy_profile_id: string | null
    id: string
    suggestion_type: string
    analysis_summary: string | null
    proposed_change: Record<string, unknown>
    status: string
  }> = await res.json()
  return all.filter(s => s.taxonomy_profile_id === profileId)
}

export default async function FamilyEditorPage({
  params,
}: {
  params: Promise<{ family: string }>
}) {
  const { family } = await params
  const headers = await authHeaders()
  const profile = await getProfile(family, headers)
  if (!profile) notFound()
  const suggestions = await getPendingSuggestions(profile.id, headers)

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-xl font-semibold font-mono">{profile.family}</h2>
        {profile.description && (
          <p className="text-muted-foreground text-sm">{profile.description}</p>
        )}
      </div>
      <SuggestionsBanner suggestions={suggestions} onAction={() => {}} />
      <WeightsEditor
        family={profile.family}
        initialWeights={profile.weights}
        initialBlockers={profile.hard_blockers}
      />
    </div>
  )
}
