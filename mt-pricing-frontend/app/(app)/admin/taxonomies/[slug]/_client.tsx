"use client";

import * as React from "react";
import { useLocale } from "next-intl";
import { toast } from "sonner";
import { AlertTriangle, Info, Pencil, Plus, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  useCreateTaxonomyNode,
  useDeleteTaxonomyNode,
  useTaxonomyNodes,
  useTaxonomyType,
  useUpdateTaxonomyNode,
} from "@/lib/hooks/use-taxonomy-registry";
import type {
  TaxonomyNodeRead,
  TaxonomyTypeRead,
} from "@/lib/api/endpoints/taxonomy-registry";

/**
 * Form-builder genérico data-driven para `TaxonomyType` arbitrarios.
 *
 * Inputs renderizados dinámicamente desde la metadata del type:
 *  - `label_i18n` keys → un input texto por locale soportado (es/en/ar).
 *  - `is_hierarchical=true` → muestra el select de parent_id.
 *  - `is_system=true` → banner read-only warning.
 *  - `ui_layout.custom_component` → placeholder warning (futuro hook).
 *
 * Reemplaza las páginas admin específicas por taxonomía. Cuando una taxonomía
 * nueva entra al registry, esta página la sirve sin código nuevo.
 */

const SUPPORTED_LOCALES = ["es", "en", "ar"] as const;
type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

const SLUG_REGEX = /^[a-z][a-z0-9_]*$/;

interface NodeFormState {
  slug: string;
  labels: Record<string, string>;
  display_order: string;
  active: boolean;
  parent_id: string; // "" means no parent
  valid_until: string; // ISO date string or ""
}

const EMPTY_FORM: NodeFormState = {
  slug: "",
  labels: { es: "", en: "", ar: "" },
  display_order: "0",
  active: true,
  parent_id: "",
  valid_until: "",
};

function fromNode(n: TaxonomyNodeRead): NodeFormState {
  const labels: Record<string, string> = { es: "", en: "", ar: "" };
  for (const k of Object.keys(n.labels ?? {})) {
    labels[k] = (n.labels?.[k] as string) ?? "";
  }
  return {
    slug: n.slug,
    labels,
    display_order: String(n.display_order ?? 0),
    active: n.active,
    parent_id: n.parent_id ?? "",
    valid_until: n.valid_until ? n.valid_until.slice(0, 10) : "",
  };
}

function resolveLabel(t: TaxonomyTypeRead, locale: string): string {
  const labels = t.label_i18n ?? {};
  return (
    labels[locale] ??
    labels.es ??
    labels.en ??
    t.slug.charAt(0).toUpperCase() + t.slug.slice(1)
  );
}

function resolveNodeLabel(n: TaxonomyNodeRead, locale: string): string {
  const labels = n.labels ?? {};
  return (
    (labels[locale] as string) ??
    (labels.es as string) ??
    (labels.en as string) ??
    n.slug
  );
}

export function TaxonomyAdminClient({ typeSlug }: { typeSlug: string }) {
  const locale = useLocale();
  const typeQ = useTaxonomyType(typeSlug);
  const nodesQ = useTaxonomyNodes(typeSlug);

  const createMut = useCreateTaxonomyNode(typeSlug);
  const updateMut = useUpdateTaxonomyNode(typeSlug);
  const deleteMut = useDeleteTaxonomyNode(typeSlug);

  const [creating, setCreating] = React.useState(false);
  const [editing, setEditing] = React.useState<TaxonomyNodeRead | null>(null);
  const [confirmDelete, setConfirmDelete] =
    React.useState<TaxonomyNodeRead | null>(null);

  // Loading / error states for `type`
  if (typeQ.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <div className="space-y-2 rounded-md border bg-background p-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      </div>
    );
  }

  if (typeQ.isError || !typeQ.data) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
        Error al cargar el tipo de taxonomía
        <code className="ml-1 font-mono">{typeSlug}</code>:{" "}
        {typeQ.error?.message ?? "tipo no encontrado"}
      </div>
    );
  }

  const type = typeQ.data;
  const nodes = nodesQ.data ?? [];
  const isHierarchical = type.is_hierarchical;
  const hasCustomComponent = !!type.ui_layout?.custom_component;
  const typeLabel = resolveLabel(type, locale);

  return (
    <>
      <header className="space-y-1">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{typeLabel}</h1>
          {type.is_system ? (
            <Badge variant="secondary" className="text-[10px] uppercase">
              Sistema
            </Badge>
          ) : null}
          {type.is_hierarchical ? (
            <Badge variant="outline" className="text-[10px] uppercase">
              Jerárquica
            </Badge>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">
          Slug:{" "}
          <code className="font-mono text-xs">{type.slug}</code> · Value kind:{" "}
          <code className="font-mono text-xs">{type.value_kind}</code>
          {type.depth_max != null ? (
            <>
              {" "}
              · Depth max:{" "}
              <code className="font-mono text-xs">{type.depth_max}</code>
            </>
          ) : null}
        </p>
      </header>

      {type.is_system ? (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>
            Tipo del sistema. Los metadatos del type (slug, hierarchical,
            value_kind) no son editables, pero podés crear, editar y borrar
            nodos.
          </span>
        </div>
      ) : null}

      {hasCustomComponent ? (
        <div className="flex items-start gap-2 rounded-md border border-blue-500/30 bg-blue-50 p-3 text-sm text-blue-800">
          <Info className="mt-0.5 size-4 shrink-0" />
          <span>
            Este tipo declara{" "}
            <code className="font-mono text-xs">
              ui_layout.custom_component =&quot;{type.ui_layout.custom_component}
              &quot;
            </code>
            . El override de componente custom todavía no está implementado;
            usando el form-builder genérico.
          </span>
        </div>
      ) : null}

      <div className="space-y-4 rounded-md border bg-background p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            {nodesQ.isLoading ? "—" : `${nodes.length} nodos`}
          </p>
          <Button onClick={() => setCreating(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Crear nodo
          </Button>
        </div>

        {nodesQ.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-md" />
            ))}
          </div>
        ) : nodesQ.isError ? (
          <p className="text-sm text-destructive">
            Error al cargar nodos: {nodesQ.error?.message}
          </p>
        ) : nodes.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No hay nodos. Pulsa &quot;Crear nodo&quot; para añadir el primero.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Slug</TableHead>
                <TableHead>Etiqueta ({locale})</TableHead>
                {isHierarchical ? <TableHead>Padre</TableHead> : null}
                <TableHead>Orden</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {nodes.map((n) => {
                const parent = isHierarchical
                  ? nodes.find((x) => x.id === n.parent_id)
                  : undefined;
                const isDeprecated =
                  !!n.valid_until &&
                  new Date(n.valid_until).getTime() <= Date.now();
                return (
                  <TableRow key={n.id}>
                    <TableCell className="font-mono text-xs">
                      {n.slug}
                    </TableCell>
                    <TableCell>{resolveNodeLabel(n, locale)}</TableCell>
                    {isHierarchical ? (
                      <TableCell className="text-xs text-muted-foreground">
                        {parent ? resolveNodeLabel(parent, locale) : "—"}
                      </TableCell>
                    ) : null}
                    <TableCell>{n.display_order}</TableCell>
                    <TableCell>
                      {isDeprecated ? (
                        <Badge variant="secondary">Deprecado</Badge>
                      ) : n.active ? (
                        <Badge>Activo</Badge>
                      ) : (
                        <Badge variant="secondary">Inactivo</Badge>
                      )}
                    </TableCell>
                    <TableCell className="space-x-1 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditing(n)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConfirmDelete(n)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}

        <NodeFormDialog
          open={creating}
          onOpenChange={setCreating}
          title={`Crear nodo en "${typeLabel}"`}
          initial={EMPTY_FORM}
          slugEditable
          isHierarchical={isHierarchical}
          nodes={nodes}
          locale={locale}
          allowDeprecation={false}
          busy={createMut.isPending}
          onSubmit={(form) => {
            // labels: drop empty values to keep payload minimal
            const labels: Record<string, string> = {};
            for (const k of SUPPORTED_LOCALES) {
              if (form.labels[k]?.trim()) labels[k] = form.labels[k].trim();
            }
            const payload: import("@/lib/api/endpoints/taxonomy-registry").TaxonomyNodeCreatePayload =
              {
                slug: form.slug,
                display_order: Number(form.display_order || 0),
                active: form.active,
                parent_id:
                  isHierarchical && form.parent_id ? form.parent_id : null,
              };
            if (Object.keys(labels).length) payload.labels = labels;
            createMut.mutate(payload, {
              onSuccess: () => {
                toast.success("Nodo creado");
                setCreating(false);
              },
              onError: (e) => toast.error(`Error al crear: ${e.message}`),
            });
          }}
        />

        <NodeFormDialog
          open={!!editing}
          onOpenChange={(o) => !o && setEditing(null)}
          title={
            editing
              ? `Editar "${resolveNodeLabel(editing, locale)}"`
              : "Editar nodo"
          }
          initial={editing ? fromNode(editing) : EMPTY_FORM}
          slugEditable={false}
          isHierarchical={isHierarchical}
          nodes={nodes.filter((n) => n.id !== editing?.id)}
          locale={locale}
          allowDeprecation
          busy={updateMut.isPending}
          onSubmit={(form) => {
            if (!editing) return;
            const labels: Record<string, string> = {};
            for (const k of SUPPORTED_LOCALES) {
              if (form.labels[k]?.trim()) labels[k] = form.labels[k].trim();
            }
            const payload: import("@/lib/api/endpoints/taxonomy-registry").TaxonomyNodeUpdatePayload =
              {
                display_order: Number(form.display_order || 0),
                active: form.active,
                valid_until: form.valid_until || null,
              };
            if (Object.keys(labels).length) payload.labels = labels;
            updateMut.mutate(
              { nodeSlug: editing.slug, payload },
              {
                onSuccess: () => {
                  toast.success("Nodo actualizado");
                  setEditing(null);
                },
                onError: (e) =>
                  toast.error(`Error al actualizar: ${e.message}`),
              },
            );
          }}
        />

        <ConfirmDialog
          open={!!confirmDelete}
          onOpenChange={(o) => !o && setConfirmDelete(null)}
          title={`Eliminar nodo "${
            confirmDelete ? resolveNodeLabel(confirmDelete, locale) : ""
          }"`}
          description="Soft-delete: el nodo se marca como deprecado (valid_until=now). Los productos vinculados conservan el link histórico."
          destructive
          confirmLabel="Eliminar"
          cancelLabel="Cancelar"
          busy={deleteMut.isPending}
          onConfirm={() => {
            if (!confirmDelete) return;
            deleteMut.mutate(confirmDelete.slug, {
              onSuccess: () => {
                toast.success("Nodo eliminado");
                setConfirmDelete(null);
              },
              onError: (e) =>
                toast.error(`Error al eliminar: ${e.message}`),
            });
          }}
        />
      </div>
    </>
  );
}

interface NodeFormDialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  initial: NodeFormState;
  slugEditable: boolean;
  isHierarchical: boolean;
  nodes: TaxonomyNodeRead[];
  locale: string;
  allowDeprecation: boolean;
  busy: boolean;
  onSubmit: (form: NodeFormState) => void;
}

const NO_PARENT = "__none__";

function NodeFormDialog({
  open,
  onOpenChange,
  title,
  initial,
  slugEditable,
  isHierarchical,
  nodes,
  locale,
  allowDeprecation,
  busy,
  onSubmit,
}: NodeFormDialogProps) {
  const [form, setForm] = React.useState<NodeFormState>(initial);
  const [slugError, setSlugError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setForm(initial);
      setSlugError(null);
    }
  }, [open, initial]);

  function validate(state: NodeFormState): string | null {
    if (slugEditable) {
      if (!state.slug) return "El slug es obligatorio.";
      if (!SLUG_REGEX.test(state.slug)) {
        return "Slug inválido. Debe empezar con letra minúscula y contener solo a-z, 0-9 y _.";
      }
    }
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            Los campos marcados con * son obligatorios. Las etiquetas vacías se
            omiten en el payload.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const err = validate(form);
            if (err) {
              setSlugError(err);
              return;
            }
            setSlugError(null);
            onSubmit(form);
          }}
          className="space-y-3"
        >
          <div className="space-y-1.5">
            <Label htmlFor="slug">Slug *</Label>
            <Input
              id="slug"
              value={form.slug}
              disabled={!slugEditable}
              onChange={(e) => {
                const v = e.target.value.toLowerCase();
                setForm({ ...form, slug: v });
                if (v && !SLUG_REGEX.test(v)) {
                  setSlugError(
                    "Slug inválido. a-z, 0-9, _; debe empezar con letra.",
                  );
                } else {
                  setSlugError(null);
                }
              }}
              required={slugEditable}
              placeholder="ej. hidrosanitario"
              className="font-mono"
            />
            {slugError ? (
              <p className="text-xs text-destructive">{slugError}</p>
            ) : !slugEditable ? (
              <p className="text-xs text-muted-foreground">
                El slug no se puede modificar tras crear el nodo.
              </p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label>Etiquetas (i18n)</Label>
            <div className="grid gap-2">
              {SUPPORTED_LOCALES.map((loc) => (
                <div
                  key={loc}
                  className="flex items-center gap-2"
                >
                  <span className="w-8 text-[11px] uppercase text-muted-foreground">
                    {loc}
                  </span>
                  <Input
                    value={form.labels[loc] ?? ""}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        labels: { ...form.labels, [loc]: e.target.value },
                      })
                    }
                    placeholder={
                      loc === locale ? "Etiqueta visible" : `Etiqueta ${loc}`
                    }
                    dir={loc === "ar" ? "rtl" : "ltr"}
                  />
                </div>
              ))}
            </div>
          </div>

          {isHierarchical ? (
            <div className="space-y-1.5">
              <Label htmlFor="parent">Nodo padre</Label>
              <Select
                value={form.parent_id || NO_PARENT}
                onValueChange={(v) =>
                  setForm({
                    ...form,
                    parent_id: v === NO_PARENT ? "" : v,
                  })
                }
              >
                <SelectTrigger id="parent">
                  <SelectValue placeholder="Sin padre (raíz)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_PARENT}>— Sin padre (raíz)</SelectItem>
                  {nodes
                    .filter((n) => n.active)
                    .map((n) => (
                      <SelectItem key={n.id} value={n.id}>
                        {resolveNodeLabel(n, locale)}{" "}
                        <span className="ml-1 text-[10px] text-muted-foreground">
                          ({n.slug})
                        </span>
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="display_order">Orden</Label>
              <Input
                id="display_order"
                type="number"
                min={0}
                max={32767}
                value={form.display_order}
                onChange={(e) =>
                  setForm({ ...form, display_order: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="active">Estado</Label>
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

          {allowDeprecation ? (
            <div className="space-y-1.5">
              <Label htmlFor="valid_until">Deprecar (valid_until)</Label>
              <Input
                id="valid_until"
                type="date"
                value={form.valid_until}
                onChange={(e) =>
                  setForm({ ...form, valid_until: e.target.value })
                }
              />
              <p className="text-xs text-muted-foreground">
                Si se establece, el nodo queda como deprecado a partir de esa
                fecha. Dejar vacío para mantenerlo vigente.
              </p>
            </div>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={busy}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={busy || !!slugError}>
              {busy ? "Guardando..." : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
