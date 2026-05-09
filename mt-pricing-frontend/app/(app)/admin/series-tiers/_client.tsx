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
  seriesTiersApi,
  type SeriesTier,
  type SeriesTierCreatePayload,
  type SeriesTierPatchPayload,
} from "@/lib/api/endpoints/series-tiers";

const KEYS = {
  all: ["admin-series-tiers"] as const,
  list: () => [...KEYS.all, "list"] as const,
};

interface FormState {
  code: string;
  name: string;
  rank: string;
  display_color: string;
  active: boolean;
}

const EMPTY: FormState = {
  code: "",
  name: "",
  rank: "99",
  display_color: "",
  active: true,
};

function fromTier(t: SeriesTier): FormState {
  return {
    code: t.code,
    name: t.name,
    rank: String(t.rank),
    display_color: t.display_color ?? "",
    active: t.active,
  };
}

export function SeriesTiersAdminClient() {
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<SeriesTier | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState<SeriesTier | null>(
    null,
  );

  const { data, isLoading, isError } = useQuery<SeriesTier[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => seriesTiersApi.list(),
    staleTime: 15_000,
  });

  const createMut = useMutation<SeriesTier, Error, SeriesTierCreatePayload>({
    mutationFn: (p) => seriesTiersApi.create(p),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Tier creado");
      setCreating(false);
    },
    onError: (e) => toast.error(`Error al crear: ${e.message}`),
  });

  const patchMut = useMutation<
    SeriesTier,
    Error,
    { id: string; payload: SeriesTierPatchPayload }
  >({
    mutationFn: ({ id, payload }) => seriesTiersApi.patch(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Tier actualizado");
      setEditing(null);
    },
    onError: (e) => toast.error(`Error al actualizar: ${e.message}`),
  });

  const deleteMut = useMutation<void, Error, string>({
    mutationFn: (id) => seriesTiersApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Tier eliminado");
      setConfirmDelete(null);
    },
    onError: (e) => toast.error(`Error al eliminar: ${e.message}`),
  });

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {data ? `${data.length} tiers` : "—"}
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
        <p className="text-sm text-destructive">Error al cargar tiers.</p>
      ) : !data || data.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hay tiers definidos.
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Rank</TableHead>
              <TableHead>Color</TableHead>
              <TableHead>Activo</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((t) => (
              <TableRow key={t.id}>
                <TableCell className="font-mono text-xs">{t.code}</TableCell>
                <TableCell>{t.name}</TableCell>
                <TableCell>{t.rank}</TableCell>
                <TableCell>
                  {t.display_color ? (
                    <span className="inline-flex items-center gap-2 text-xs">
                      <span
                        className="inline-block h-4 w-4 rounded border"
                        style={{ background: t.display_color }}
                      />
                      <span className="font-mono">{t.display_color}</span>
                    </span>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>
                  {t.active ? (
                    <Badge>Activo</Badge>
                  ) : (
                    <Badge variant="secondary">Inactivo</Badge>
                  )}
                </TableCell>
                <TableCell className="space-x-1 text-right">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setEditing(t)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setConfirmDelete(t)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <TierFormDialog
        open={creating}
        onOpenChange={setCreating}
        title="Crear tier"
        initial={EMPTY}
        codeEditable
        busy={createMut.isPending}
        onSubmit={(form) =>
          createMut.mutate({
            code: form.code,
            name: form.name,
            rank: Number(form.rank || 99),
            display_color: form.display_color || null,
            active: form.active,
          })
        }
      />

      <TierFormDialog
        open={!!editing}
        onOpenChange={(o) => !o && setEditing(null)}
        title="Editar tier"
        initial={editing ? fromTier(editing) : EMPTY}
        codeEditable={false}
        busy={patchMut.isPending}
        onSubmit={(form) => {
          if (!editing) return;
          patchMut.mutate({
            id: editing.id,
            payload: {
              name: form.name,
              rank: Number(form.rank || 99),
              display_color: form.display_color || null,
              active: form.active,
            },
          });
        }}
      />

      <ConfirmDialog
        open={!!confirmDelete}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        title={`Eliminar "${confirmDelete?.name ?? ""}"`}
        description="Esta acción no se puede deshacer si el tier no tiene series asociadas."
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

function TierFormDialog({
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
              pattern="^[a-z][a-z0-9_]{0,31}$"
              placeholder="platinum"
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
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="rank">Rank (1-99)</Label>
              <Input
                id="rank"
                type="number"
                min={1}
                max={99}
                value={form.rank}
                onChange={(e) => setForm({ ...form, rank: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="display_color">Color</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="display_color"
                  value={form.display_color}
                  onChange={(e) =>
                    setForm({ ...form, display_color: e.target.value })
                  }
                  placeholder="#0ea5e9"
                  maxLength={16}
                />
                {form.display_color ? (
                  <span
                    className="inline-block h-8 w-8 shrink-0 rounded border"
                    style={{ background: form.display_color }}
                  />
                ) : null}
              </div>
            </div>
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
