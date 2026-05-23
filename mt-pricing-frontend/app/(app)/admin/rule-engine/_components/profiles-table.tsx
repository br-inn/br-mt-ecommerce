"use client"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ChevronRight } from "lucide-react"

interface Profile {
  id: string
  family: string
  weights: Record<string, number>
  hard_blockers: string[]
  description: string | null
}

const DIM_LABEL: Record<string, string> = {
  material: "Material",
  pn: "PN",
  dn: "DN",
  product_type: "Tipo",
  thread_standard: "Rosca",
  ways: "Vías",
  norma: "Norma",
  brand_tier: "Tier",
  delivery: "Entrega",
  data_completeness: "Datos",
}

function WeightBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? (value / max) * 100 : 0
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="h-1.5 rounded-full bg-muted flex-shrink-0 w-16 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary/60"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function Weights({ weights }: { weights: Record<string, number> }) {
  const sorted = Object.entries(weights)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)

  if (sorted.length === 0)
    return <span className="text-muted-foreground text-xs">sin configurar</span>

  const maxVal = sorted[0]![1]
  const top = sorted.slice(0, 5)
  const rest = sorted.length - top.length

  return (
    <div className="space-y-1">
      {top.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground w-16 shrink-0">
            {DIM_LABEL[k] ?? k}
          </span>
          <WeightBar value={v} max={maxVal} />
          <span className="text-xs font-mono tabular-nums w-8 text-right">
            {(v * 100).toFixed(0)}%
          </span>
        </div>
      ))}
      {rest > 0 && (
        <div className="text-xs text-muted-foreground">+{rest} más</div>
      )}
    </div>
  )
}

function Blockers({ blockers }: { blockers: string[] }) {
  if (blockers.length === 0)
    return <span className="text-muted-foreground text-xs">ninguno</span>
  return (
    <div className="flex flex-col gap-1">
      {blockers.map((b) => (
        <Badge
          key={b}
          variant="secondary"
          className="font-mono font-normal text-xs w-fit"
        >
          {b}
        </Badge>
      ))}
    </div>
  )
}

export function ProfilesTable({
  profiles,
  suggestionCounts,
}: {
  profiles: Profile[]
  suggestionCounts: Record<string, number>
}) {
  return (
    <div className="rounded-md border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium w-[18%]">Familia</th>
            <th className="px-4 py-3 text-left font-medium w-[38%]">
              Pesos por dimensión
            </th>
            <th className="px-4 py-3 text-left font-medium w-[30%]">
              Hard Blockers
            </th>
            <th className="px-4 py-3 text-left font-medium w-[10%]">
              Sugerencias
            </th>
            <th className="px-4 py-3 w-[4%]" />
          </tr>
        </thead>
        <tbody>
          {profiles.map((p) => {
            const pending = suggestionCounts[p.id] ?? 0
            return (
              <tr
                key={p.id}
                className="border-b last:border-0 hover:bg-muted/30 transition-colors group"
              >
                <td className="px-4 py-4 align-top">
                  <span className="font-mono font-medium text-sm">
                    {p.family}
                  </span>
                  {p.description && (
                    <div className="text-xs text-muted-foreground mt-0.5 leading-snug">
                      {p.description}
                    </div>
                  )}
                </td>
                <td className="px-4 py-4 align-top">
                  <Weights weights={p.weights} />
                </td>
                <td className="px-4 py-4 align-top">
                  <Blockers blockers={p.hard_blockers} />
                </td>
                <td className="px-4 py-4 align-top">
                  {pending > 0 ? (
                    <Badge
                      variant="outline"
                      className="text-yellow-600 border-yellow-400 whitespace-nowrap"
                    >
                      {pending} IA
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-4 align-top text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="opacity-0 group-hover:opacity-100 transition-opacity h-7 px-2"
                    asChild
                  >
                    <Link
                      href={`/admin/rule-engine/${encodeURIComponent(p.family)}`}
                    >
                      Editar
                      <ChevronRight className="size-3.5 ml-0.5" />
                    </Link>
                  </Button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
