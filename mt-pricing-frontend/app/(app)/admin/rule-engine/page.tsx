import { ProfileCard } from "./_components/profile-card"
import { Button } from "@/components/ui/button"
import Link from "next/link"

async function getTaxonomyProfiles() {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/rule-engine/taxonomy-profiles`,
    { cache: "no-store" }
  )
  if (!res.ok) return []
  return res.json()
}

async function getSuggestionCounts(): Promise<Record<string, number>> {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/v1/rule-engine/rule-suggestions?status=pending`,
    { cache: "no-store" }
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
  const [profiles, suggestionCounts] = await Promise.all([
    getTaxonomyProfiles(),
    getSuggestionCounts(),
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {profiles.map((p: { id: string; family: string }) => (
          <ProfileCard
            key={p.id}
            family={p.family}
            pendingSuggestions={suggestionCounts[p.id] ?? 0}
          />
        ))}
      </div>
    </div>
  )
}
