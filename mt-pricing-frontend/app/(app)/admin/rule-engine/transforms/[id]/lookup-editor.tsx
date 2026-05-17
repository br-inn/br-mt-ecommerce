"use client"
import { useState, useRef, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { toast } from "sonner"
import { ArrowLeft, Plus, Trash2 } from "lucide-react"
import env from "@/lib/env"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

interface Transform {
  id: string
  transform_type: string
  from_unit: string
  to_unit: string
  formula: string | null
  lookup_table: Record<string, string> | null
  description: string | null
}

type Row = { id: number; key: string; value: string }

let _seq = 0
const nextSeq = () => ++_seq

function tableToRows(table: Record<string, unknown> | null): Row[] {
  if (!table) return []
  return Object.entries(table).map(([k, v]) => ({
    id: nextSeq(),
    key: k,
    value: String(v),
  }))
}

function rowsToTable(rows: Row[]): Record<string, string> {
  return Object.fromEntries(
    rows.filter((r) => r.key.trim()).map((r) => [r.key.trim(), r.value.trim()]),
  )
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

export function LookupEditor({ transform }: { transform: Transform }) {
  const router = useRouter()
  const [fromUnit, setFromUnit] = useState(transform.from_unit)
  const [toUnit, setToUnit] = useState(transform.to_unit)
  const [description, setDescription] = useState(transform.description ?? "")
  const [rows, setRows] = useState<Row[]>(() => tableToRows(transform.lookup_table))
  const [saving, setSaving] = useState(false)
  const lastRowRef = useRef<HTMLInputElement>(null)
  const [focusLast, setFocusLast] = useState(false)

  useEffect(() => {
    if (focusLast) {
      lastRowRef.current?.focus()
      setFocusLast(false)
    }
  }, [focusLast, rows])

  const addRow = () => {
    setRows((prev) => [...prev, { id: nextSeq(), key: "", value: "" }])
    setFocusLast(true)
  }

  const updateRow = (id: number, field: "key" | "value", val: string) =>
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: val } : r)))

  const removeRow = (id: number) =>
    setRows((prev) => prev.filter((r) => r.id !== id))

  const handleSave = async () => {
    if (!fromUnit.trim() || !toUnit.trim()) {
      toast.error("Los campos «De» y «A» son obligatorios")
      return
    }
    setSaving(true)
    try {
      const authHeader = await getAuthHeader()
      const res = await fetch(
        `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/unit-transforms/${transform.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json", ...authHeader },
          body: JSON.stringify({
            transform_type: transform.transform_type,
            from_unit: fromUnit.trim(),
            to_unit: toUnit.trim(),
            formula: null,
            lookup_table: rowsToTable(rows),
            description: description.trim() || null,
          }),
        },
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        toast.error(err?.detail ?? "Error al guardar")
        return
      }
      toast.success("Transformación guardada")
      router.push("/admin/rule-engine/transforms")
    } finally {
      setSaving(false)
    }
  }

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLInputElement>,
    rowId: number,
    field: "key" | "value",
  ) => {
    if (e.key === "Tab" && !e.shiftKey && field === "value") {
      const isLast = rows[rows.length - 1]?.id === rowId
      if (isLast) {
        e.preventDefault()
        addRow()
      }
    }
    if (e.key === "Enter") {
      e.preventDefault()
      if (field === "key") {
        // move to value of same row
        const tr = (e.target as HTMLElement).closest("tr")
        const next = tr?.querySelectorAll("input")[1] as HTMLInputElement | null
        next?.focus()
      } else {
        addRow()
      }
    }
  }

  const isLookup = transform.transform_type === "lookup" || transform.transform_type === "nominal"

  return (
    <div className="space-y-6">
      {/* Breadcrumb / back */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <button
          onClick={() => router.push("/admin/rule-engine/transforms")}
          className="hover:text-foreground flex items-center gap-1 transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          Transformaciones
        </button>
        <span>/</span>
        <Badge variant="outline">{transform.transform_type}</Badge>
        <span className="font-mono text-foreground">
          {fromUnit || transform.from_unit} → {toUnit || transform.to_unit}
        </span>
      </div>

      {/* Metadata fields */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl">
        <div className="space-y-1.5">
          <Label>De (unidad origen)</Label>
          <Input
            value={fromUnit}
            onChange={(e) => setFromUnit(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>A (unidad destino)</Label>
          <Input
            value={toUnit}
            onChange={(e) => setToUnit(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>
            Descripción{" "}
            <span className="text-muted-foreground">(opcional)</span>
          </Label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
      </div>

      {/* Lookup table editor */}
      {isLookup && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium">Tabla de conversión</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {rows.length} {rows.length === 1 ? "entrada" : "entradas"} ·
                Tab en último campo para añadir fila · Enter para avanzar
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={addRow}>
              <Plus className="size-4 mr-2" />
              Agregar fila
            </Button>
          </div>

          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2.5 text-left font-medium">
                    {fromUnit || "Clave (origen)"}
                  </th>
                  <th className="px-4 py-2.5 text-left font-medium">
                    {toUnit || "Valor (destino)"}
                  </th>
                  <th className="w-10 px-3" />
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-4 py-8 text-center text-muted-foreground"
                    >
                      Sin entradas.{" "}
                      <button
                        className="underline underline-offset-2 hover:text-foreground"
                        onClick={addRow}
                      >
                        Agrega la primera fila
                      </button>
                    </td>
                  </tr>
                )}
                {rows.map((row, idx) => {
                  const isLastRow = idx === rows.length - 1
                  return (
                    <tr key={row.id} className="border-b last:border-0 group">
                      <td className="px-2 py-1">
                        <Input
                          ref={isLastRow ? lastRowRef : undefined}
                          value={row.key}
                          onChange={(e) =>
                            updateRow(row.id, "key", e.target.value)
                          }
                          onKeyDown={(e) => handleKeyDown(e, row.id, "key")}
                          className="font-mono h-8 border-transparent bg-transparent shadow-none focus-visible:border-input focus-visible:bg-background"
                          placeholder="clave"
                        />
                      </td>
                      <td className="px-2 py-1">
                        <Input
                          value={row.value}
                          onChange={(e) =>
                            updateRow(row.id, "value", e.target.value)
                          }
                          onKeyDown={(e) => handleKeyDown(e, row.id, "value")}
                          className="font-mono h-8 border-transparent bg-transparent shadow-none focus-visible:border-input focus-visible:bg-background"
                          placeholder="valor"
                        />
                      </td>
                      <td className="px-2 py-1 text-right">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-7 opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive transition-opacity"
                          onClick={() => removeRow(row.id)}
                          tabIndex={-1}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2 border-t">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Guardando..." : "Guardar cambios"}
        </Button>
        <Button
          variant="outline"
          onClick={() => router.push("/admin/rule-engine/transforms")}
          disabled={saving}
        >
          Cancelar
        </Button>
      </div>
    </div>
  )
}
