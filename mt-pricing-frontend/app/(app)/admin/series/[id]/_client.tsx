"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Plus, Trash2, X } from "lucide-react";

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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  seriesApi,
  type Series,
  type SeriesLang,
  type SeriesPatchPayload,
  type SeriesTranslation,
} from "@/lib/api/endpoints/series";
import {
  seriesTiersApi,
  type SeriesTier,
} from "@/lib/api/endpoints/series-tiers";
import {
  divisionsApi,
  type Division,
} from "@/lib/api/endpoints/divisions";
import {
  certificationsApi,
  type Certification,
} from "@/lib/api/endpoints/certifications";

const KEYS = {
  detail: (id: string) => ["admin-series", "detail", id] as const,
  translations: (id: string) =>
    ["admin-series", "translations", id] as const,
  tiers: ["admin-series-tiers", "list"] as const,
  divisions: ["admin-divisions", "list"] as const,
  seriesDivisions: (id: string) =>
    ["admin-series", "divisions", id] as const,
  certifications: ["admin-certifications", "list"] as const,
  seriesCertifications: (id: string) =>
    ["admin-series", "certifications", id] as const,
};

const TIER_NONE = "__none__";

interface DetailProps {
  seriesId: string;
}

export function SeriesDetailClient({ seriesId }: DetailProps) {
  const { data, isLoading, isError } = useQuery<Series, Error>({
    queryKey: KEYS.detail(seriesId),
    queryFn: () => seriesApi.getPublic(seriesId),
    staleTime: 5_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-72" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="space-y-3">
        <Button asChild variant="ghost">
          <Link href="/admin/series">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Volver
          </Link>
        </Button>
        <p className="text-sm text-destructive">
          No se pudo cargar la serie.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Button asChild variant="ghost" size="sm">
          <Link href="/admin/series">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Volver al listado
          </Link>
        </Button>
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {data.name_en}
            </h1>
            <p className="font-mono text-xs text-muted-foreground">
              {data.code}
            </p>
          </div>
          {data.active ? (
            <Badge>Activo</Badge>
          ) : (
            <Badge variant="secondary">Inactivo</Badge>
          )}
        </header>
      </div>

      <Tabs defaultValue="general" className="space-y-4">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="translations">Traducciones</TabsTrigger>
          <TabsTrigger value="divisions">Divisiones</TabsTrigger>
          <TabsTrigger value="certifications">Certificaciones</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <GeneralTab series={data} />
        </TabsContent>
        <TabsContent value="translations">
          <TranslationsTab seriesId={seriesId} />
        </TabsContent>
        <TabsContent value="divisions">
          <DivisionsTab seriesId={seriesId} />
        </TabsContent>
        <TabsContent value="certifications">
          <CertificationsTab seriesId={seriesId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// General tab
// ---------------------------------------------------------------------------

interface GeneralFormState {
  name_en: string;
  tier_id: string;
  pressure_rating_pn: string;
  banner_color: string;
  hero_image_url: string;
  description_en: string;
  bullets_en: string[];
  features_tags: string[];
  sort_order: string;
  active: boolean;
}

function fromSeries(s: Series): GeneralFormState {
  return {
    name_en: s.name_en,
    tier_id: s.tier_id ?? TIER_NONE,
    pressure_rating_pn:
      s.pressure_rating_pn === null ? "" : String(s.pressure_rating_pn),
    banner_color: s.banner_color ?? "",
    hero_image_url: s.hero_image_url ?? "",
    description_en: s.description_en ?? "",
    bullets_en: [...s.bullets_en],
    features_tags: [...s.features_tags],
    sort_order: String(s.sort_order),
    active: s.active,
  };
}

function GeneralTab({ series }: { series: Series }) {
  const qc = useQueryClient();
  const [form, setForm] = React.useState<GeneralFormState>(fromSeries(series));

  React.useEffect(() => {
    setForm(fromSeries(series));
  }, [series]);

  const { data: tiers } = useQuery<SeriesTier[], Error>({
    queryKey: KEYS.tiers,
    queryFn: () => seriesTiersApi.list(),
    staleTime: 60_000,
  });

  const patchMut = useMutation<Series, Error, SeriesPatchPayload>({
    mutationFn: (payload) => seriesApi.patch(series.id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.detail(series.id) });
      toast.success("Serie actualizada");
    },
    onError: (e) => toast.error(`Error al actualizar: ${e.message}`),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    patchMut.mutate({
      name_en: form.name_en,
      tier_id: form.tier_id === TIER_NONE ? null : form.tier_id,
      pressure_rating_pn:
        form.pressure_rating_pn === "" ? null : Number(form.pressure_rating_pn),
      banner_color: form.banner_color || null,
      hero_image_url: form.hero_image_url || null,
      description_en: form.description_en || null,
      bullets_en: form.bullets_en,
      features_tags: form.features_tags,
      sort_order: Number(form.sort_order || 0),
      active: form.active,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 rounded-md border bg-background p-6"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="code">Código</Label>
          <Input
            id="code"
            value={series.code}
            disabled
            className="font-mono"
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
              {(tiers ?? []).map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pressure_rating_pn">Presión nominal (PN)</Label>
          <Input
            id="pressure_rating_pn"
            type="number"
            min={0}
            max={10000}
            value={form.pressure_rating_pn}
            onChange={(e) =>
              setForm({ ...form, pressure_rating_pn: e.target.value })
            }
            placeholder="40"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="banner_color">Color de banner</Label>
          <div className="flex items-center gap-2">
            <Input
              id="banner_color"
              value={form.banner_color}
              onChange={(e) =>
                setForm({ ...form, banner_color: e.target.value })
              }
              maxLength={32}
              placeholder="#0ea5e9"
            />
            {form.banner_color ? (
              <span
                className="inline-block h-9 w-9 shrink-0 rounded border"
                style={{ background: form.banner_color }}
              />
            ) : null}
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="hero_image_url">URL del hero image</Label>
          <Input
            id="hero_image_url"
            value={form.hero_image_url}
            onChange={(e) =>
              setForm({ ...form, hero_image_url: e.target.value })
            }
            maxLength={2048}
            placeholder="https://…"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description_en">Descripción (EN)</Label>
        <textarea
          id="description_en"
          value={form.description_en}
          onChange={(e) =>
            setForm({ ...form, description_en: e.target.value })
          }
          rows={4}
          maxLength={4000}
          className="flex min-h-[96px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        />
      </div>

      <ArrayEditor
        label="Bullets (EN)"
        items={form.bullets_en}
        onChange={(items) => setForm({ ...form, bullets_en: items })}
        placeholder="Añadir bullet…"
      />

      <ArrayEditor
        label="Características (tags)"
        items={form.features_tags}
        onChange={(items) => setForm({ ...form, features_tags: items })}
        placeholder="Añadir tag…"
      />

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="sort_order">Orden</Label>
          <Input
            id="sort_order"
            type="number"
            min={0}
            max={32767}
            value={form.sort_order}
            onChange={(e) => setForm({ ...form, sort_order: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="active">Activo</Label>
          <div className="flex h-9 items-center gap-2">
            <input
              id="active"
              type="checkbox"
              checked={form.active}
              onChange={(e) => setForm({ ...form, active: e.target.checked })}
              className="h-4 w-4"
            />
            <span className="text-sm text-muted-foreground">
              {form.active ? "Activo" : "Inactivo"}
            </span>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t pt-4">
        <Button
          type="button"
          variant="ghost"
          onClick={() => setForm(fromSeries(series))}
        >
          Descartar cambios
        </Button>
        <Button type="submit" disabled={patchMut.isPending}>
          {patchMut.isPending ? "Guardando..." : "Guardar"}
        </Button>
      </div>
    </form>
  );
}

interface ArrayEditorProps {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}

function ArrayEditor({ label, items, onChange, placeholder }: ArrayEditorProps) {
  const [draft, setDraft] = React.useState("");
  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onChange([...items, v]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground">Sin elementos.</p>
      ) : (
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li
              key={`${i}-${it}`}
              className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-1.5 text-sm"
            >
              <span className="break-all">{it}</span>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onChange(items.filter((_, j) => j !== i))}
              >
                <X className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={placeholder ?? "Añadir…"}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={add}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Translations tab
// ---------------------------------------------------------------------------

const LANGS: SeriesLang[] = ["es", "ar", "en"];

function TranslationsTab({ seriesId }: { seriesId: string }) {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery<SeriesTranslation[], Error>({
    queryKey: KEYS.translations(seriesId),
    queryFn: () => seriesApi.listTranslationsPublic(seriesId),
    staleTime: 10_000,
  });

  const upsertMut = useMutation<
    SeriesTranslation,
    Error,
    { lang: SeriesLang; name: string; description: string; bullets: string[] }
  >({
    mutationFn: ({ lang, name, description, bullets }) =>
      seriesApi.upsertTranslation(seriesId, lang, {
        lang,
        name,
        description: description || null,
        bullets,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.translations(seriesId) });
      toast.success("Traducción guardada");
    },
    onError: (e) => toast.error(`Error al guardar: ${e.message}`),
  });

  const deleteMut = useMutation<void, Error, SeriesLang>({
    mutationFn: (lang) => seriesApi.deleteTranslation(seriesId, lang),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.translations(seriesId) });
      toast.success("Traducción eliminada");
    },
    onError: (e) => toast.error(`Error al eliminar: ${e.message}`),
  });

  if (isLoading) return <Skeleton className="h-48 w-full" />;
  if (isError) {
    return (
      <p className="text-sm text-destructive">
        Error al cargar traducciones.
      </p>
    );
  }

  const byLang = new Map<SeriesLang, SeriesTranslation>();
  (data ?? []).forEach((t) => byLang.set(t.lang as SeriesLang, t));

  return (
    <div className="space-y-4">
      {LANGS.map((lang) => (
        <TranslationRow
          key={lang}
          lang={lang}
          existing={byLang.get(lang) ?? null}
          busy={upsertMut.isPending || deleteMut.isPending}
          onSave={(name, description, bullets) =>
            upsertMut.mutate({ lang, name, description, bullets })
          }
          onDelete={() => deleteMut.mutate(lang)}
        />
      ))}
    </div>
  );
}

interface TranslationRowProps {
  lang: SeriesLang;
  existing: SeriesTranslation | null;
  busy: boolean;
  onSave: (name: string, description: string, bullets: string[]) => void;
  onDelete: () => void;
}

function TranslationRow({
  lang,
  existing,
  busy,
  onSave,
  onDelete,
}: TranslationRowProps) {
  const [name, setName] = React.useState(existing?.name ?? "");
  const [description, setDescription] = React.useState(
    existing?.description ?? "",
  );
  const [bullets, setBullets] = React.useState<string[]>(
    existing?.bullets ?? [],
  );

  React.useEffect(() => {
    setName(existing?.name ?? "");
    setDescription(existing?.description ?? "");
    setBullets(existing?.bullets ?? []);
  }, [existing]);

  return (
    <div className="space-y-3 rounded-md border bg-background p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide">
          {lang}
        </h3>
        {existing ? (
          <Badge variant="outline">Definida</Badge>
        ) : (
          <Badge variant="secondary">Sin traducción</Badge>
        )}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Nombre</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label>Descripción</Label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          maxLength={4000}
          className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        />
      </div>
      <ArrayEditor
        label="Bullets"
        items={bullets}
        onChange={setBullets}
        placeholder="Añadir bullet…"
      />
      <div className="flex justify-end gap-2 border-t pt-3">
        {existing ? (
          <Button
            type="button"
            variant="ghost"
            disabled={busy}
            onClick={onDelete}
          >
            <Trash2 className="mr-2 h-4 w-4 text-destructive" />
            Eliminar
          </Button>
        ) : null}
        <Button
          type="button"
          disabled={busy || !name}
          onClick={() => onSave(name, description, bullets)}
        >
          Guardar
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Divisions tab
// ---------------------------------------------------------------------------

function DivisionsTab({ seriesId }: { seriesId: string }) {
  const qc = useQueryClient();
  const [adding, setAdding] = React.useState<string>("");

  // Recordatorio: el backend no expone un endpoint dedicado para "series ↔
  // divisions" como GET, así que filtramos `seriesApi.listPublic({division_id})`
  // en cliente. Como atajo, listamos las divisiones y para cada una probamos
  // pertenencia consultando la lista filtrada por division_id. Suficiente
  // para el MVP — al haber pocas divisiones esto es < 10 calls.
  const { data: divisions, isLoading: divisionsLoading } = useQuery<
    Division[],
    Error
  >({
    queryKey: KEYS.divisions,
    queryFn: () => divisionsApi.list(),
    staleTime: 30_000,
  });

  // Para cada division, traemos las series filtradas y resolvemos pertenencia.
  const seriesByDivisionQueries = useQuery<Set<string>, Error>({
    queryKey: KEYS.seriesDivisions(seriesId),
    enabled: !!divisions,
    queryFn: async () => {
      if (!divisions) return new Set<string>();
      const memberships = await Promise.all(
        divisions.map(async (d) => {
          const list = await seriesApi.listPublic({ division_id: d.id });
          return list.some((s) => s.id === seriesId) ? d.id : null;
        }),
      );
      return new Set(memberships.filter((x): x is string => !!x));
    },
    staleTime: 10_000,
  });

  const linkMut = useMutation<void, Error, string>({
    mutationFn: (divId) => seriesApi.linkDivision(seriesId, divId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.seriesDivisions(seriesId) });
      toast.success("División añadida");
      setAdding("");
    },
    onError: (e) => toast.error(`Error al añadir: ${e.message}`),
  });

  const unlinkMut = useMutation<void, Error, string>({
    mutationFn: (divId) => seriesApi.unlinkDivision(seriesId, divId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.seriesDivisions(seriesId) });
      toast.success("División removida");
    },
    onError: (e) => toast.error(`Error al remover: ${e.message}`),
  });

  if (divisionsLoading || seriesByDivisionQueries.isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  const memberSet = seriesByDivisionQueries.data ?? new Set<string>();
  const members = (divisions ?? []).filter((d) => memberSet.has(d.id));
  const candidates = (divisions ?? []).filter((d) => !memberSet.has(d.id));

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Divisiones asociadas</h3>
        {members.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin divisiones asociadas.
          </p>
        ) : (
          <ul className="space-y-1">
            {members.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-1.5 text-sm"
              >
                <span>
                  <span className="font-mono text-xs">{d.code}</span>
                  {" — "}
                  {d.name}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={unlinkMut.isPending}
                  onClick={() => unlinkMut.mutate(d.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-2 border-t pt-4">
        <Label>Añadir división</Label>
        <div className="flex gap-2">
          <Select value={adding} onValueChange={setAdding}>
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Selecciona división…" />
            </SelectTrigger>
            <SelectContent>
              {candidates.length === 0 ? (
                <div className="p-2 text-xs text-muted-foreground">
                  Sin candidatos.
                </div>
              ) : (
                candidates.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <Button
            type="button"
            disabled={!adding || linkMut.isPending}
            onClick={() => linkMut.mutate(adding)}
          >
            <Plus className="mr-2 h-4 w-4" />
            Añadir
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Certifications tab
// ---------------------------------------------------------------------------

function CertificationsTab({ seriesId }: { seriesId: string }) {
  const [adding, setAdding] = React.useState<string>("");
  const [members, setMembers] = React.useState<Certification[]>([]);

  // Como el backend no expone GET de junction series ↔ cert, mantenemos la
  // membresía en estado local optimista — se recarga desde 0 al volver a la
  // pestaña. Es aceptable para el MVP de gestión interna.
  const { data: certifications, isLoading } = useQuery<
    Certification[],
    Error
  >({
    queryKey: KEYS.certifications,
    queryFn: () => certificationsApi.list(),
    staleTime: 60_000,
  });

  const linkMut = useMutation<void, Error, Certification>({
    mutationFn: (cert) => seriesApi.linkCertification(seriesId, cert.id),
    onSuccess: (_void, cert) => {
      setMembers((m) =>
        m.find((c) => c.id === cert.id) ? m : [...m, cert],
      );
      toast.success("Certificación añadida");
      setAdding("");
    },
    onError: (e) => toast.error(`Error al añadir: ${e.message}`),
  });

  const unlinkMut = useMutation<void, Error, string>({
    mutationFn: (certId) => seriesApi.unlinkCertification(seriesId, certId),
    onSuccess: (_void, certId) => {
      setMembers((m) => m.filter((c) => c.id !== certId));
      toast.success("Certificación removida");
    },
    onError: (e) => toast.error(`Error al remover: ${e.message}`),
  });

  // Persistir la membresía actual la dejamos como mejora futura (faltan
  // endpoints GET en backend para series ↔ certifications).

  if (isLoading) return <Skeleton className="h-48 w-full" />;

  const memberIds = new Set(members.map((c) => c.id));
  const candidates = (certifications ?? []).filter(
    (c) => !memberIds.has(c.id),
  );
  const candidatesById = new Map(candidates.map((c) => [c.id, c]));

  return (
    <div className="space-y-4 rounded-md border bg-background p-4">
      <div className="rounded-md border border-amber-500/30 bg-amber-50 p-3 text-xs text-amber-800">
        Aviso: el backend no expone aún un GET de la asociación series ↔
        certificaciones, por lo que la lista se mantiene sólo en memoria
        durante la sesión. Refresca la página y vuelve a sumar las
        certificaciones tras un cambio si lo necesitas persistente.
      </div>
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Certificaciones asociadas</h3>
        {members.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin certificaciones asociadas en esta sesión.
          </p>
        ) : (
          <ul className="space-y-1">
            {members.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-1.5 text-sm"
              >
                <span>
                  <span className="font-mono text-xs">{c.code}</span>
                  {" — "}
                  {c.name}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={unlinkMut.isPending}
                  onClick={() => unlinkMut.mutate(c.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-2 border-t pt-4">
        <Label>Añadir certificación</Label>
        <div className="flex gap-2">
          <Select value={adding} onValueChange={setAdding}>
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Selecciona certificación…" />
            </SelectTrigger>
            <SelectContent>
              {candidates.length === 0 ? (
                <div className="p-2 text-xs text-muted-foreground">
                  Sin candidatos.
                </div>
              ) : (
                candidates.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))
              )}
            </SelectContent>
          </Select>
          <Button
            type="button"
            disabled={!adding || linkMut.isPending}
            onClick={() => {
              const cert = candidatesById.get(adding);
              if (cert) linkMut.mutate(cert);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            Añadir
          </Button>
        </div>
      </div>
    </div>
  );
}
