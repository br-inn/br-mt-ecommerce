"use client"
import { useState } from "react"
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
import { Textarea } from "@/components/ui/textarea"
import { toast } from "sonner"
import { Pencil, Plus, Trash2 } from "lucide-react"
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
  lookup_table: string
  description: string
}

const EMPTY_FORM: FormState = {
  transform_type: "numeric",
  from_unit: "",
  to_unit: "",
  formula: "",
  lookup_table: "{}",
  description: "",
}

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
    lookup_table: t.lookup_table ? JSON.stringify(t.lookup_table, null, 2) : "{}",
    description: t.description ?? "",
  }
}

function formToPayload(f: FormState) {
  const needsLookup = f.transform_type === "lookup" || f.transform_type === "nominal"
  let lookup_table: Record<string, unknown> | null = null
  if (needsLookup) {
    try {
      lookup_table = JSON.parse(f.lookup_table)
    } catch {
      throw new Error("La tabla de conversión no es JSON válido")
    }
  }
  return {
    transform_type: f.transform_type,
    from_unit: f.from_unit.trim(),
    to_unit: f.to_unit.trim(),
    formula: f.transform_type === "numeric" ? f.formula.trim() || null : null,
    lookup_table,
    description: f.description.trim() || null,
  }
}

type DialogState =
  | null
  | { mode: "create" }
  | { mode: "edit"; item: Transform }

export function TransformsTable({ initialData }: { initialData: Transform[] }) {
  const [transforms, setTransforms] = useState(initialData)
  const [dialog, setDialog] = useState<DialogState>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setDialog({ mode: "create" })
  }

  const openEdit = (item: Transform) => {
    setForm(transformToForm(item))
    setDialog({ mode: "edit", item })
  }

  const closeDialog = () => {
    if (!saving) setDialog(null)
  }

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      let payload: ReturnType<typeof formToPayload>
      try {
        payload = formToPayload(form)
      } catch (e) {
        toast.error((e as Error).message)
        return
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
        toast.success("Transformación creada")
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
      }
      setDialog(null)
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

  const needsLookupTable =
    form.transform_type === "lookup" || form.transform_type === "nominal"

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
              <th className="px-4 py-3 text-left font-medium">Fórmula / Lookup</th>
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
            {transforms.map((t) => (
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
                  <div className="flex gap-1 justify-end">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8"
                      title="Editar"
                      onClick={() => openEdit(t)}
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
            ))}
          </tbody>
        </table>
      </div>

      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => {
          if (!open) closeDialog()
        }}
      >
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create"
                ? "Nueva transformación"
                : "Editar transformación"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
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

            {needsLookupTable && (
              <div className="space-y-1.5">
                <Label>Tabla de conversión (JSON)</Label>
                <Textarea
                  placeholder={'{\n  "DN15": "NPS_0.5in",\n  "DN20": "NPS_0.75in"\n}'}
                  value={form.lookup_table}
                  onChange={(e) => setField("lookup_table", e.target.value)}
                  className="font-mono text-xs min-h-[120px]"
                />
              </div>
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
                  ? "Crear"
                  : "Guardar cambios"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
