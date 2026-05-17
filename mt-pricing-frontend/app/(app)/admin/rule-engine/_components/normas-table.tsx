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
import { toast } from "sonner"
import { Pencil, Plus, Trash2 } from "lucide-react"
import env from "@/lib/env"
import { createSupabaseBrowserClient } from "@/lib/supabase/client"

interface NormEquivalence {
  id: string
  norm_a: string
  system_a: string
  norm_b: string
  system_b: string
  equivalence_type: string
  notes: string | null
}

type FormState = {
  norm_a: string
  system_a: string
  norm_b: string
  system_b: string
  equivalence_type: string
  notes: string
}

const EMPTY_FORM: FormState = {
  norm_a: "",
  system_a: "",
  norm_b: "",
  system_b: "",
  equivalence_type: "exact",
  notes: "",
}

const EQUIV_TYPE_LABELS: Record<string, string> = {
  exact: "exact — completamente equivalentes",
  subset: "subset — una norma es subconjunto de la otra",
  compatible: "compatible — uso intercambiable en contexto",
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()
  if (!session?.access_token) return {}
  return { Authorization: `Bearer ${session.access_token}` }
}

function normToForm(n: NormEquivalence): FormState {
  return {
    norm_a: n.norm_a,
    system_a: n.system_a,
    norm_b: n.norm_b,
    system_b: n.system_b,
    equivalence_type: n.equivalence_type,
    notes: n.notes ?? "",
  }
}

type DialogState =
  | null
  | { mode: "create" }
  | { mode: "edit"; item: NormEquivalence }

export function NormasTable({ initialData }: { initialData: NormEquivalence[] }) {
  const [norms, setNorms] = useState(initialData)
  const [dialog, setDialog] = useState<DialogState>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setDialog({ mode: "create" })
  }

  const openEdit = (item: NormEquivalence) => {
    setForm(normToForm(item))
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
      const payload = {
        norm_a: form.norm_a.trim(),
        system_a: form.system_a.trim(),
        norm_b: form.norm_b.trim(),
        system_b: form.system_b.trim(),
        equivalence_type: form.equivalence_type,
        notes: form.notes.trim() || null,
      }
      if (!payload.norm_a || !payload.system_a || !payload.norm_b || !payload.system_b) {
        toast.error("Norma A, Sistema A, Norma B y Sistema B son obligatorios")
        return
      }
      const authHeader = await getAuthHeader()
      if (dialog?.mode === "create") {
        const res = await fetch(
          `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/norm-equivalences`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json", ...authHeader },
            body: JSON.stringify(payload),
          },
        )
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          toast.error(err?.detail ?? "Error al crear equivalencia")
          return
        }
        const created: NormEquivalence = await res.json()
        setNorms((prev) => [...prev, created])
        toast.success("Equivalencia creada")
      } else if (dialog?.mode === "edit") {
        const res = await fetch(
          `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/norm-equivalences/${dialog.item.id}`,
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
        const updated: NormEquivalence = await res.json()
        setNorms((prev) => prev.map((n) => (n.id === updated.id ? updated : n)))
        toast.success("Equivalencia actualizada")
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
        `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/rule-engine/norm-equivalences/${id}`,
        { method: "DELETE", headers: authHeader },
      )
      if (!res.ok) {
        toast.error("Error al eliminar")
        return
      }
      setNorms((prev) => prev.filter((n) => n.id !== id))
      toast.success("Equivalencia eliminada")
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openCreate}>
          <Plus className="size-4 mr-2" />
          Nueva equivalencia
        </Button>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left font-medium">Norma A</th>
              <th className="px-4 py-3 text-left font-medium">Sistema A</th>
              <th className="px-4 py-3 text-left font-medium">Norma B</th>
              <th className="px-4 py-3 text-left font-medium">Sistema B</th>
              <th className="px-4 py-3 text-left font-medium">Tipo</th>
              <th className="px-4 py-3 text-left font-medium">Notas</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {norms.length === 0 && (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  Sin equivalencias. Usa «Nueva equivalencia» para agregar.
                </td>
              </tr>
            )}
            {norms.map((n) => (
              <tr key={n.id} className="border-b last:border-0">
                <td className="px-4 py-3 font-mono">{n.norm_a}</td>
                <td className="px-4 py-3">
                  <Badge variant="secondary">{n.system_a}</Badge>
                </td>
                <td className="px-4 py-3 font-mono">{n.norm_b}</td>
                <td className="px-4 py-3">
                  <Badge variant="secondary">{n.system_b}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge variant="outline">{n.equivalence_type}</Badge>
                </td>
                <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">
                  {n.notes ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 justify-end">
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8"
                      title="Editar"
                      onClick={() => openEdit(n)}
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="size-8 text-destructive hover:text-destructive"
                      title="Eliminar"
                      onClick={() => handleDelete(n.id)}
                      disabled={deletingId === n.id}
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
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create"
                ? "Nueva equivalencia de norma"
                : "Editar equivalencia"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Norma A</Label>
                <Input
                  placeholder="PN16"
                  value={form.norm_a}
                  onChange={(e) => setField("norm_a", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Sistema A</Label>
                <Input
                  placeholder="DIN / ISO / ASME"
                  value={form.system_a}
                  onChange={(e) => setField("system_a", e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Norma B</Label>
                <Input
                  placeholder="Class 150"
                  value={form.norm_b}
                  onChange={(e) => setField("norm_b", e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Sistema B</Label>
                <Input
                  placeholder="ANSI / ASME"
                  value={form.system_b}
                  onChange={(e) => setField("system_b", e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Tipo de equivalencia</Label>
              <Select
                value={form.equivalence_type}
                onValueChange={(v) => setField("equivalence_type", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(EQUIV_TYPE_LABELS).map(([v, label]) => (
                    <SelectItem key={v} value={v}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>
                Notas{" "}
                <span className="text-muted-foreground">(opcional)</span>
              </Label>
              <Input
                placeholder="Equivalentes para rangos DN15-DN600"
                value={form.notes}
                onChange={(e) => setField("notes", e.target.value)}
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
