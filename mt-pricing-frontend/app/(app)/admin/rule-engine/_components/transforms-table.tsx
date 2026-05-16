"use client"
import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { toast } from "sonner"

interface Transform {
  id: string
  transform_type: string
  from_unit: string
  to_unit: string
  formula: string | null
  description: string | null
}

export function TransformsTable({ initialData }: { initialData: Transform[] }) {
  const [transforms, setTransforms] = useState(initialData)
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? ""

  const handleDelete = async (id: string) => {
    const res = await fetch(`${apiBase}/api/v1/rule-engine/unit-transforms/${id}`, {
      method: "DELETE",
    })
    if (!res.ok) {
      toast.error("Error al eliminar")
      return
    }
    setTransforms(prev => prev.filter(t => t.id !== id))
    toast.success("Transformación eliminada")
  }

  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium">Tipo</th>
            <th className="px-4 py-3 text-left font-medium">De</th>
            <th className="px-4 py-3 text-left font-medium">A</th>
            <th className="px-4 py-3 text-left font-medium">Fórmula / Lookup</th>
            <th className="px-4 py-3 text-left font-medium">Descripción</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {transforms.map(t => (
            <tr key={t.id} className="border-b last:border-0">
              <td className="px-4 py-3">
                <Badge variant="outline">{t.transform_type}</Badge>
              </td>
              <td className="px-4 py-3 font-mono">{t.from_unit}</td>
              <td className="px-4 py-3 font-mono">{t.to_unit}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {t.formula ?? "(lookup table)"}
              </td>
              <td className="px-4 py-3">{t.description}</td>
              <td className="px-4 py-3">
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive hover:text-destructive"
                  onClick={() => handleDelete(t.id)}
                >
                  Eliminar
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
