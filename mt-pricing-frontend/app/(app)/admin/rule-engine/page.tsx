import { ProfilesTable } from "./_components/profiles-table"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import env from "@/lib/env"
import { createClient } from "@/lib/supabase/server"

const apiBase = process.env.BACKEND_URL ?? env.NEXT_PUBLIC_BACKEND_URL

async function authHeaders(): Promise<HeadersInit> {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

async function getTaxonomyProfiles(headers: HeadersInit) {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/taxonomy-profiles`,
    { cache: "no-store", headers }
  )
  if (!res.ok) return []
  return res.json()
}

async function getSuggestionCounts(headers: HeadersInit): Promise<Record<string, number>> {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/rule-suggestions?status=pending`,
    { cache: "no-store", headers }
  )
  if (!res.ok) return {}
  const suggestions: Array<{ taxonomy_profile_id: string | null }> = await res.json()
  return suggestions.reduce<Record<string, number>>((acc, s) => {
    if (s.taxonomy_profile_id) {
      acc[s.taxonomy_profile_id] = (acc[s.taxonomy_profile_id] ?? 0) + 1
    }
    return acc
  }, {})
}

export default async function RuleEnginePage() {
  const headers = await authHeaders()
  const [profiles, suggestionCounts] = await Promise.all([
    getTaxonomyProfiles(headers),
    getSuggestionCounts(headers),
  ])

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">{profiles.length} familias configuradas</p>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/admin/rule-engine/transforms">Transformaciones de unidades</Link>
          </Button>
        </div>
      </div>
      <ProfilesTable profiles={profiles} suggestionCounts={suggestionCounts} />
    </div>
  )
}
