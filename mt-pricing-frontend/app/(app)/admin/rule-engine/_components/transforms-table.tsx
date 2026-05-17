"use client"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { toast } from "sonner"
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react"
import env from "@/lib/env"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

interface Transform {
  id: string
  transform_type: string
  from_unit: string
  to_unit: string
  formula: string | null
  lookup_table: Record<string, unknown> | null
  description: string | null
}

type FormState = {
  transform_type: string
  from_unit: string
  to_unit: string
  formula: string
  description: string
}

const EMPTY_FORM: FormState = {
  transform_type: "numeric",
  from_unit: "",
  to_unit: "",
  formula: "",
  description: "",
}

const isLookupType = (t: string) => t === "lookup" || t === "nominal"

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

function transformToForm(t: Transform): FormState {
  return {
    transform_type: t.transform_type,
    from_unit: t.from_unit,
    to_unit: t.to_unit,
    formula: t.formula ?? "",
    description: t.description ?? "",
  }
}

type DialogState =
  | null
  | { mode: "create" }
  | { mode: "edit"; item: Transform }

export function TransformsTable({ initialData }: { initialData: Transform[] }) {
  const router = useRouter()
  const [transforms, setTransforms] = useState(initialData)
  const [dialog, setDialog] = useState<DialogState>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setDialog({ mode: "create" })
  }

  const handleEdit = (item: Transform) => {
    if (isLookupType(item.transform_type)) {
      router.push(`/admin/rule-engine/transforms/${item.id}`)
    } else {
      setForm(transformToForm(item))
      setDialog({ mode: "edit", item })
    }
  }

  const closeDialog = () => {
    if (!saving) setDialog(null)
  }

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const payload = {
        transform_type: form.transform_type,
        from_unit: form.from_unit.trim(),
        to_unit: form.to_unit.trim(),
        formula: form.transform_type === "numeric" ? form.formula.trim() || null : null,
        lookup_table: isLookupType(form.transform_type) ? {} : null,
        description: form.description.trim() || null,
      }
      if (!payload.from_unit || !payload.to_unit) {
        toast.error("Los campos «De» y «A» son obligatorios")
        return
      }
      const authHeader = await getAuthHeader()

      if (dialog?.mode === "create") {
        const res = await fetch(
          `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/unit-transforms`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeader },
            body: JSON.stringify(payload),
          },
        )
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          toast.error(err?.detail ?? "Error al crear transformación")
          return
        }
        const created: Transform = await res.json()
        setTransforms((prev) => [...prev, created])
        setDialog(null)

        if (isLookupType(created.transform_type)) {
          toast.success("Transformación creada — ahora agrega las entradas de la tabla")
          router.push(`/admin/rule-engine/transforms/${created.id}`)
        } else {
          toast.success("Transformación creada")
        }
      } else if (dialog?.mode === "edit") {
        const res = await fetch(
          `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/unit-transforms/${dialog.item.id}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json", ...authHeader },
            body: JSON.stringify(payload),
          },
        )
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          toast.error(err?.detail ?? "Error al guardar cambios")
          return
        }
        const updated: Transform = await res.json()
        setTransforms((prev) => prev.map((t) => (t.id === updated.id ? updated : t)))
        toast.success("Transformación actualizada")
        setDialog(null)
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    setDeletingId(id)
    try {
      const authHeader = await getAuthHeader()
      const res = await fetch(
        `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/unit-transforms/${id}`,
        { method: "DELETE", headers: authHeader },
      )
      if (!res.ok) {
        toast.error("Error al eliminar")
        return
      }
      setTransforms((prev) => prev.filter((t) => t.id !== id))
      toast.success("Transformación eliminada")
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openCreate}>
          <Plus className="size-4 mr-2" />
          Nueva transformación
        </Button>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left font-medium">Tipo</th>
              <th className="px-4 py-3 text-left font-medium">De</th>
              <th className="px-4 py-3 text-left font-medium">A</th>
              <th className="px-4 py-3 text-left font-medium">Fórmula / Entradas</th>
              <th className="px-4 py-3 text-left font-medium">Descripción</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {transforms.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  Sin transformaciones. Usa «Nueva transformación» para agregar.
                </td>
              </tr>
            )}
            {transforms.map((t) => {
              const isLookup = isLookupType(t.transform_type)
              const entryCount = t.lookup_table
                ? Object.keys(t.lookup_table).length
                : 0
              return (
                <tr key={t.id} className="border-b last:border-0">
                  <td className="px-4 py-3">
                    <Badge variant="outline">{t.transform_type}</Badge>
                  </td>
                  <td className="px-4 py-3 font-mono">{t.from_unit}</td>
                  <td className="px-4 py-3 font-mono">{t.to_unit}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {isLookup ? (
                      <button
                        className="flex items-center gap-1.5 hover:text-foreground transition-colors"
                        onClick={() => router.push(`/admin/rule-engine/transforms/${t.id}`)}
                      >
                        <ExternalLink className="size-3.5 shrink-0" />
                        {entryCount} {entryCount === 1 ? "entrada" : "entradas"}
                      </button>
                    ) : (
                      t.formula
                    )}
                  </td>
                  <td className="px-4 py-3">{t.description}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1 justify-end">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8"
                        title={isLookup ? "Editar tabla" : "Editar"}
                        onClick={() => handleEdit(t)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-8 text-destructive hover:text-destructive"
                        title="Eliminar"
                        onClick={() => handleDelete(t.id)}
                        disabled={deletingId === t.id}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Modal — solo para numeric (create + edit) y create de lookup/nominal */}
      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => {
          if (!open) closeDialog()
        }}
      >
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create"
                ? "Nueva transformación"
                : "Editar transformación"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Tipo — solo editable en create */}
            {dialog?.mode === "create" && (
              <div className="space-y-1.5">
                <Label>Tipo</Label>
                <Select
                  value={form.transform_type}
                  onValueChange={(v) => setField("transform_type", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="numeric">
                      numeric — fórmula matemática
                    </SelectItem>
                    <SelectItem value="lookup">
                      lookup — tabla de conversión
                    </SelectItem>
                    <SelectItem value="nominal">
                      nominal — equivalencias nominales
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>De (unidad origen)</Label>
                <Input
                  placeholder="PSI"
                  value={form.from_unit}
                  onChange={(e) => setField("from_unit", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>A (unidad destino)</Label>
                <Input
                  placeholder="PN"
                  value={form.to_unit}
                  onChange={(e) => setField("to_unit", e.target.value)}
                />
              </div>
            </div>

            {/* Fórmula: solo para numeric */}
            {form.transform_type === "numeric" && (
              <div className="space-y-1.5">
                <Label>Fórmula</Label>
                <Input
                  placeholder="floor({value} / 14.5038)"
                  value={form.formula}
                  onChange={(e) => setField("formula", e.target.value)}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Usa{" "}
                  <code className="font-mono bg-muted px-1 rounded">
                    {"{value}"}
                  </code>{" "}
                  como placeholder del valor a convertir.
                </p>
              </div>
            )}

            {/* Aviso para lookup/nominal */}
            {isLookupType(form.transform_type) && dialog?.mode === "create" && (
              <p className="text-xs text-muted-foreground rounded-md bg-muted px-3 py-2">
                Tras crear, se abrirá el editor de tabla para agregar las
                entradas de conversión.
              </p>
            )}

            <div className="space-y-1.5">
              <Label>
                Descripción{" "}
                <span className="text-muted-foreground">(opcional)</span>
              </Label>
              <Input
                placeholder="PSI/WOG a PN (presión nominal bar)"
                value={form.description}
                onChange={(e) => setField("description", e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog} disabled={saving}>
              Cancelar
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving
                ? "Guardando..."
                : dialog?.mode === "create"
                  ? isLookupType(form.transform_type)
                    ? "Crear y editar tabla →"
                    : "Crear"
                  : "Guardar cambios"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
