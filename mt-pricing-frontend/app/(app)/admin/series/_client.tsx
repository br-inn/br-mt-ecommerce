"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Eye, Plus } from "lucide-react";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  seriesApi,
  type Series,
  type SeriesCreatePayload,
} from "@/lib/api/endpoints/series";
import {
  seriesTiersApi,
  type SeriesTier,
} from "@/lib/api/endpoints/series-tiers";

const KEYS = {
  all: ["admin-series"] as const,
  list: () => [...KEYS.all, "list"] as const,
};

const TIER_NONE = "__none__";

interface CreateFormState {
  code: string;
  name_en: string;
  tier_id: string;
  active: boolean;
}

const EMPTY_CREATE: CreateFormState = {
  code: "",
  name_en: "",
  tier_id: TIER_NONE,
  active: true,
};

export function SeriesAdminListClient() {
  const qc = useQueryClient();
  const [creating, setCreating] = React.useState(false);
  const [search, setSearch] = React.useState("");

  const { data, isLoading, isError } = useQuery<Series[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => seriesApi.list(),
    staleTime: 15_000,
  });

  const { data: tiers } = useQuery<SeriesTier[], Error>({
    queryKey: ["admin-series-tiers", "list"],
    queryFn: () => seriesTiersApi.list(),
    staleTime: 60_000,
  });

  const createMut = useMutation<Series, Error, SeriesCreatePayload>({
    mutationFn: (p) => seriesApi.create(p),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all });
      toast.success("Serie creada");
      setCreating(false);
    },
    onError: (e) => toast.error(`Error al crear: ${e.message}`),
  });

  const filtered = React.useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data;
    const q = search.trim().toLowerCase();
    return data.filter(
      (s) =>
        s.code.toLowerCase().includes(q) ||
        s.name_en.toLowerCase().includes(q),
    );
  }, [data, search]);

  const tierByID = React.useMemo(() => {
    const map = new Map<string, SeriesTier>();
    (tiers ?? []).forEach((t) => map.set(t.id, t));
    return map;
  }, [tiers]);

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs font-medium text-muted-foreground">
            Buscar
          </Label>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Código o nombre…"
            className="w-72"
          />
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Crear
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">Error al cargar series.</p>
      ) : filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {data && data.length === 0
            ? 'No hay series. Pulsa "Crear" para añadir la primera.'
            : "Sin coincidencias para la búsqueda."}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Código</TableHead>
              <TableHead>Nombre (EN)</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead>PN</TableHead>
              <TableHead>Orden</TableHead>
              <TableHead>Activo</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((s) => {
              const tier = s.tier_id ? tierByID.get(s.tier_id) : undefined;
              return (
                <TableRow key={s.id}>
                  <TableCell className="font-mono text-xs">{s.code}</TableCell>
                  <TableCell>{s.name_en}</TableCell>
                  <TableCell>
                    {tier ? (
                      <Badge variant="outline">{tier.name}</Badge>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell>
                    {s.pressure_rating_pn ?? "—"}
                  </TableCell>
                  <TableCell>{s.sort_order}</TableCell>
                  <TableCell>
                    {s.active ? (
                      <Badge>Activo</Badge>
                    ) : (
                      <Badge variant="secondary">Inactivo</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button asChild size="sm" variant="ghost">
                      <Link href={`/admin/series/${s.id}`}>
                        <Eye className="h-4 w-4" />
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      <CreateSeriesDialog
        open={creating}
        onOpenChange={setCreating}
        tiers={tiers ?? []}
        busy={createMut.isPending}
        onSubmit={(form) =>
          createMut.mutate({
            code: form.code,
            name_en: form.name_en,
            tier_id: form.tier_id === TIER_NONE ? null : form.tier_id,
            active: form.active,
          })
        }
      />
    </div>
  );
}

interface CreateDialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  tiers: SeriesTier[];
  busy: boolean;
  onSubmit: (form: CreateFormState) => void;
}

function CreateSeriesDialog({
  open,
  onOpenChange,
  tiers,
  busy,
  onSubmit,
}: CreateDialogProps) {
  const [form, setForm] = React.useState<CreateFormState>(EMPTY_CREATE);
  React.useEffect(() => {
    if (open) setForm(EMPTY_CREATE);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Crear serie</DialogTitle>
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
              onChange={(e) =>
                setForm({ ...form, code: e.target.value.toLowerCase() })
              }
              required
              pattern="^[a-z][a-z0-9_]{0,63}$"
              placeholder="pn40_platinum"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name_en">Nombre (EN)</Label>
            <Input
              id="name_en"
              value={form.name_en}
              onChange={(e) => setForm({ ...form, name_en: e.target.value })}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label>Tier</Label>
            <Select
              value={form.tier_id}
              onValueChange={(v) => setForm({ ...form, tier_id: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="—" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TIER_NONE}>—</SelectItem>
                {tiers.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
          <p className="text-xs text-muted-foreground">
            Después de crear podrás añadir descripción, bullets, divisiones,
            certificaciones y traducciones desde el detalle.
          </p>
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={busy}>
              {busy ? "Guardando..." : "Crear"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
