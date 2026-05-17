import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TransformsTable } from "../_components/transforms-table"
import env from "@/lib/env"

async function getTransforms() {
  const res = await fetch(
    `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/unit-transforms`,
    { cache: "no-store" }
  )
  if (!res.ok) return []
  return res.json()
}

async function getNormEquivalences() {
  const res = await fetch(
    `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/norm-equivalences`,
    { cache: "no-store" }
  )
  if (!res.ok) return []
  return res.json()
}

export default async function TransformsPage() {
  const [transforms, norms] = await Promise.all([getTransforms(), getNormEquivalences()])

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
        <p className="text-sm text-muted-foreground">
          Equivalencias DIN ↔ ISO ↔ ASME. Tabla en construcción.
        </p>
      </TabsContent>
    </Tabs>
  )
}
