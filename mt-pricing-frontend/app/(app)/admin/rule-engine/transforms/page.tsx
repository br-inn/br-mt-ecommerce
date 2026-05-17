import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TransformsTable } from "../_components/transforms-table"
import { NormasTable } from "../_components/normas-table"
import env from "@/lib/env"
import { createClient } from "@/lib/supabase/server"

const apiBase = process.env.BACKEND_URL ?? env.NEXT_PUBLIC_BACKEND_URL

async function authHeaders(): Promise<HeadersInit> {
  const supabase = await createClient()
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

async function getTransforms(headers: HeadersInit) {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/unit-transforms`,
    { cache: "no-store", headers }
  )
  if (!res.ok) return []
  return res.json()
}

async function getNormEquivalences(headers: HeadersInit) {
  const res = await fetch(
    `${apiBase}/api/v1/rule-engine/norm-equivalences`,
    { cache: "no-store", headers }
  )
  if (!res.ok) return []
  return res.json()
}

export default async function TransformsPage() {
  const headers = await authHeaders()
  const [transforms, norms] = await Promise.all([getTransforms(headers), getNormEquivalences(headers)])

  return (
    <Tabs defaultValue="units">
      <TabsList>
        <TabsTrigger value="units">Unidades ({transforms.length})</TabsTrigger>
        <TabsTrigger value="norms">Normas ({norms.length})</TabsTrigger>
      </TabsList>
      <TabsContent value="units" className="mt-4">
        <TransformsTable initialData={transforms} />
      </TabsContent>
      <TabsContent value="norms" className="mt-4">
        <NormasTable initialData={norms} />
      </TabsContent>
    </Tabs>
  )
}
