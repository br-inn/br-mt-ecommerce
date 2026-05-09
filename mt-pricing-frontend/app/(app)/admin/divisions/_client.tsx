"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
  divisionsApi,
  type Division,
  type DivisionCreatePayload,
  type DivisionPatchPayload,
} from "@/lib/api/endpoints/divisions";

const KEYS = {
  all: ["admin-divisions"] as const,
  list: () => [...KEYS.all, "list"] as const,
};

interface FormState {
  code: string;
  name: string;
  description: string;
  sort_order: string;
  active: boolean;
}

const EMPTY: FormState = {
  code: "",
  name: "",
  description: "",
  sort_order: "0",
  active: true,
};

function fromDivision(d: Division): FormState {
  return {
    code: d.code,
    name: d.name,
    description: d.description ?? "",
    sort_order: String(d.sort_order),
    active: d.active,
  };
}

export function DivisionsAdminClient() {
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<Division | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState<Division | null>(
    null,
  );

  const { data, isLoading, isError } = useQuery<Division[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => divisionsApi.list(),
    staleTime: 15_000,
  });

  const createMut = useMutation<Division, Error, DivisionCreatePayload>({
    mutationFn: (p) => divisionsApi.create(p),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("División creada");
      setCreating(false);
    },
    onError: (e) => toast.error(`Error al crear: ${e.message}`),
  });

  const patchMut = useMutation<
    Division,
    Error,
    { id: string; payload: DivisionPatchPayload }
  >({
    mutationFn: ({ id, payload }) => divisionsApi.patch(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("División actualizada");
      setEditing(null);
    },
    onError: (e) => toast.error(`Error al actualizar: ${e.message}`),
  });

  const deleteMut = useMutation<void, Error, string>({
    mutationFn: (id) => divisionsApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("División eliminada");
      setConfirmDelete(null);
    },
    onError: (e) => toast.error(`Error al eliminar: ${e.message}`),
  });

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {data ? `${data.length} divisiones` : "—"}
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
        <p className="text-sm text-destructive">Error al cargar divisiones.</p>
      ) : !data || data.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hay divisiones. Pulsa &quot;Crear&quot; para añadir la primera.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Descripción</TableHead>
              <TableHead>Orden</TableHead>
              <TableHead>Activo</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-mono text-xs">{d.code}</TableCell>
                <TableCell>{d.name}</TableCell>
                <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                  {d.description ?? "—"}
                </TableCell>
                <TableCell>{d.sort_order}</TableCell>
                <TableCell>
                  {d.active ? (
                    <Badge>Activo</Badge>
                  ) : (
                    <Badge variant="secondary">Inactivo</Badge>
                  )}
                </TableCell>
                <TableCell className="space-x-1 text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditing(d)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setConfirmDelete(d)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* Create dialog */}
      <DivisionFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Crear división"
        initial={EMPTY}
        codeEditable
        busy={createMut.isPending}
        onSubmit={(form) =>
          createMut.mutate({
            code: form.code,
            name: form.name,
            description: form.description || null,
            sort_order: Number(form.sort_order || 0),
            active: form.active,
          })
        }
      />

      {/* Edit dialog */}
      <DivisionFormDialog
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar división"
        initial={editing ? fromDivision(editing) : EMPTY}
        codeEditable={false}
        busy={patchMut.isPending}
        onSubmit={(form) => {
          if (!editing) return;
          patchMut.mutate({
            id: editing.id,
            payload: {
              name: form.name,
              description: form.description || null,
              sort_order: Number(form.sort_order || 0),
              active: form.active,
            },
          });
        }}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`Eliminar "${confirmDelete?.name ?? ""}"`}
        description="Esta acción no se puede deshacer si la división no tiene productos asociados."
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

function DivisionFormDialog({
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
              placeholder="hidrosanitario"
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
            <Label htmlFor="description">Descripción</Label>
            <textarea
              id="description"
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
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
