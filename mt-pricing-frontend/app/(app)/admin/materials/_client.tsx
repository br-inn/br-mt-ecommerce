"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  materialsApi,
  type Material,
  type MaterialCreatePayload,
  type MaterialPatchPayload,
} from "@/lib/api/endpoints/materials";

const KEYS = {
  all: ["admin-materials"] as const,
  list: () => [...KEYS.all, "list"] as const,
};

const FAMILY_KIND_NONE = "__none__";

interface FormState {
  code: string;
  name: string;
  family_kind: string;
  notes: string;
  sort_order: string;
  active: boolean;
}

const EMPTY: FormState = {
  code: "",
  name: "",
  family_kind: FAMILY_KIND_NONE,
  notes: "",
  sort_order: "0",
  active: true,
};

function fromMaterial(m: Material): FormState {
  return {
    code: m.code,
    name: m.name,
    family_kind: m.family_kind ?? FAMILY_KIND_NONE,
    notes: m.notes ?? "",
    sort_order: String(m.sort_order),
    active: m.active,
  };
}

export function MaterialsAdminClient() {
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<Material | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState<Material | null>(
    null,
  );

  const { data, isLoading, isError } = useQuery<Material[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => materialsApi.list(),
    staleTime: 15_000,
  });

  const createMut = useMutation<Material, Error, MaterialCreatePayload>({
    mutationFn: (p) => materialsApi.create(p),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Material creado");
      setCreating(false);
    },
    onError: (e) => toast.error(`Error al crear: ${e.message}`),
  });

  const patchMut = useMutation<
    Material,
    Error,
    { id: string; payload: MaterialPatchPayload }
  >({
    mutationFn: ({ id, payload }) => materialsApi.patch(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Material actualizado");
      setEditing(null);
    },
    onError: (e) => toast.error(`Error al actualizar: ${e.message}`),
  });

  const deleteMut = useMutation<void, Error, string>({
    mutationFn: (id) => materialsApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Material eliminado");
      setConfirmDelete(null);
    },
    onError: (e) => toast.error(`Error al eliminar: ${e.message}`),
  });

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {data ? `${data.length} materiales` : "—"}
        </p>
        <Button onClick={() => setCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Crear
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">
          Error al cargar materiales.
        </p>
      ) : !data || data.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hay materiales. Pulsa &quot;Crear&quot; para añadir el primero.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Familia</TableHead>
              <TableHead>Notas</TableHead>
              <TableHead>Orden</TableHead>
              <TableHead>Activo</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-mono text-xs">{m.code}</TableCell>
                <TableCell>{m.name}</TableCell>
                <TableCell className="text-xs">
                  {m.family_kind ?? "—"}
                </TableCell>
                <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                  {m.notes ?? "—"}
                </TableCell>
                <TableCell>{m.sort_order}</TableCell>
                <TableCell>
                  {m.active ? (
                    <Badge>Activo</Badge>
                  ) : (
                    <Badge variant="secondary">Inactivo</Badge>
                  )}
                </TableCell>
                <TableCell className="space-x-1 text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditing(m)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setConfirmDelete(m)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <MaterialFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Crear material"
        initial={EMPTY}
        codeEditable
        busy={createMut.isPending}
        onSubmit={(form) =>
          createMut.mutate({
            code: form.code,
            name: form.name,
            family_kind:
              form.family_kind === FAMILY_KIND_NONE ? null : form.family_kind,
            notes: form.notes || null,
            sort_order: Number(form.sort_order || 0),
            active: form.active,
          })
        }
      />

      <MaterialFormDialog
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar material"
        initial={editing ? fromMaterial(editing) : EMPTY}
        codeEditable={false}
        busy={patchMut.isPending}
        onSubmit={(form) => {
          if (!editing) return;
          patchMut.mutate({
            id: editing.id,
            payload: {
              name: form.name,
              family_kind:
                form.family_kind === FAMILY_KIND_NONE ? null : form.family_kind,
              notes: form.notes || null,
              sort_order: Number(form.sort_order || 0),
              active: form.active,
            },
          });
        }}
      />

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`Eliminar "${confirmDelete?.name ?? ""}"`}
        description="Esta acción no se puede deshacer si el material no está en uso."
        destructive
        confirmLabel="Eliminar"
        cancelLabel="Cancelar"
        busy={deleteMut.isPending}
        onConfirm={() => {
          if (confirmDelete) deleteMut.mutate(confirmDelete.id);
        }}
      />
    </div>
  );
}

interface FormDialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  initial: FormState;
  codeEditable: boolean;
  busy: boolean;
  onSubmit: (form: FormState) => void;
}

function MaterialFormDialog({
  open,
  onOpenChange,
  title,
  initial,
  codeEditable,
  busy,
  onSubmit,
}: FormDialogProps) {
  const [form, setForm] = React.useState<FormState>(initial);
  React.useEffect(() => {
    if (open) setForm(initial);
  }, [open, initial]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit(form);
          }}
          className="space-y-3"
        >
          <div className="space-y-1.5">
            <Label htmlFor="code">Código</Label>
            <Input
              id="code"
              value={form.code}
              disabled={!codeEditable}
              onChange={(e) =>
                setForm({ ...form, code: e.target.value.toLowerCase() })
              }
              required
              pattern="^[a-z][a-z0-9_]{0,63}$"
              placeholder="laton"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name">Nombre</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Tipo de familia</Label>
            <Select
              value={form.family_kind}
              onValueChange={(v) => setForm({ ...form, family_kind: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecciona…" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FAMILY_KIND_NONE}>—</SelectItem>
                <SelectItem value="metal">metal</SelectItem>
                <SelectItem value="polymer">polymer</SelectItem>
                <SelectItem value="composite">composite</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="notes">Notas</Label>
            <textarea
              id="notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={3}
              maxLength={1024}
              className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="sort_order">Orden</Label>
              <Input
                id="sort_order"
                type="number"
                min={0}
                max={32767}
                value={form.sort_order}
                onChange={(e) =>
                  setForm({ ...form, sort_order: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="active">Activo</Label>
              <div className="flex h-9 items-center gap-2">
                <input
                  id="active"
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) =>
                    setForm({ ...form, active: e.target.checked })
                  }
                  className="h-4 w-4"
                />
                <span className="text-sm text-muted-foreground">
                  {form.active ? "Activo" : "Inactivo"}
                </span>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
