"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Pencil, Plus, X } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
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
import {
  scraperSourcesApi,
  ScraperSourcesApiError,
  type AnalyzeResponse,
  type DestinationProfile,
  type RecipeFieldDef,
  type ScraperSourceRead,
} from "@/lib/api/endpoints/scraper-sources";
import { scraperSourceKeys, useAnalyzeUrl } from "@/lib/hooks/admin/use-scraper-sources";

const REQUIRED_FIELD_NAMES = new Set(["external_id", "title", "price_aed"]);

function extractApiErrorMessage(err: unknown): string {
  if (err instanceof ScraperSourcesApiError) {
    const d = err.detail;
    if (typeof d === "object" && d !== null && "detail" in d) {
      return String((d as { detail: unknown }).detail);
    }
    if (typeof d === "string") return d;
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Error inesperado al conectar con el servidor";
}

type Step = "url-form" | "analyzing" | "review" | "creating";

const urlFormSchema = z.object({
  url: z.string().url("Ingresa una URL válida (incluye https://)"),
  context: z.string().max(500).optional(),
  destination_profile: z.enum(["competitor_price", "product_data"]),
});
type UrlFormValues = z.infer<typeof urlFormSchema>;

const fieldSchema = z.object({
  name: z
    .string()
    .min(1)
    .max(64)
    .regex(/^[a-z_][a-z0-9_]*$/, "Solo letras minúsculas, números y guión bajo"),
  selector: z.string().min(1, "El selector CSS es requerido"),
  extract: z.string().min(1),
  type: z.enum(["str", "float", "int", "currency", "bool"]),
});
type FieldFormValues = z.infer<typeof fieldSchema>;

interface Props {
  mode: "create" | "edit";
  source?: ScraperSourceRead;
  open: boolean;
  onClose: () => void;
  onSuccess?: (source: ScraperSourceRead) => void;
}

export function SourceDialog({ mode: _mode, source: _source, open, onClose, onSuccess }: Props) {
  const qc = useQueryClient();
  const analyzeUrl = useAnalyzeUrl();

  const [step, setStep] = React.useState<Step>("url-form");
  const [analyzeResult, setAnalyzeResult] = React.useState<AnalyzeResponse | null>(null);
  const [originalUrl, setOriginalUrl] = React.useState("");
  const [editedFields, setEditedFields] = React.useState<RecipeFieldDef[]>([]);
  const [destProfile, setDestProfile] = React.useState<DestinationProfile>("competitor_price");
  const [editingIndex, setEditingIndex] = React.useState<number | null>(null);
  const [addingField, setAddingField] = React.useState<"ai" | "manual" | null>(null);
  const [aiHint, setAiHint] = React.useState("");
  const [createError, setCreateError] = React.useState<string | null>(null);

  const urlForm = useForm<UrlFormValues>({
    resolver: zodResolver(urlFormSchema),
    defaultValues: { url: "", context: "", destination_profile: "competitor_price" },
  });

  const fieldForm = useForm<FieldFormValues>({
    resolver: zodResolver(fieldSchema),
    defaultValues: { name: "", selector: "", extract: "text", type: "str" },
  });

  React.useEffect(() => {
    if (!open) {
      setStep("url-form");
      setAnalyzeResult(null);
      setOriginalUrl("");
      setEditedFields([]);
      setEditingIndex(null);
      setAddingField(null);
      setAiHint("");
      setCreateError(null);
      urlForm.reset();
      fieldForm.reset();
    }
  }, [open, urlForm, fieldForm]);

  const missingRequired = [...REQUIRED_FIELD_NAMES].filter(
    (name) => !editedFields.some((f) => f.name === name),
  );
  const canCreate = missingRequired.length === 0;

  // ── Step 1 handler ──────────────────────────────────────────────────────
  const handleAnalyze = async (values: UrlFormValues) => {
    setStep("analyzing");
    setDestProfile(values.destination_profile);
    try {
      const result = await analyzeUrl.mutateAsync({
        url: values.url,
        context: values.context ?? null,
      });
      setAnalyzeResult(result);
      setEditedFields(result.proposed_recipe.fields ?? []);
      setOriginalUrl(values.url);
      setStep("review");
    } catch (err) {
      setStep("url-form");
      const msg = extractApiErrorMessage(err);
      toast.error(msg);
    }
  };

  // ── Field editing handlers ───────────────────────────────────────────────
  const handleEditField = (index: number) => {
    const f = editedFields[index]!;
    fieldForm.reset({ name: f.name, selector: f.selector, extract: f.extract, type: f.type });
    setEditingIndex(index);
    setAddingField(null);
  };

  const handleSaveEdit = (values: FieldFormValues) => {
    if (editingIndex === null) return;
    setEditedFields((prev) =>
      prev.map((f, i) =>
        i === editingIndex
          ? { name: values.name, selector: values.selector, extract: values.extract, type: values.type, transform: f.transform }
          : f,
      ),
    );
    setEditingIndex(null);
    fieldForm.reset();
  };

  const handleRemoveField = (index: number) => {
    setEditedFields((prev) => prev.filter((_, i) => i !== index));
    if (editingIndex === index) setEditingIndex(null);
  };

  const handleAddManual = (values: FieldFormValues) => {
    setEditedFields((prev) => [
      ...prev,
      { name: values.name, selector: values.selector, extract: values.extract, type: values.type, transform: null },
    ]);
    setAddingField(null);
    fieldForm.reset();
  };

  const handleFindWithAI = async () => {
    if (!aiHint.trim()) return;
    try {
      const result = await analyzeUrl.mutateAsync({
        url: originalUrl,
        hint: aiHint.trim(),
      });
      const newField = result.proposed_recipe.fields?.[0];
      if (newField) {
        setEditedFields((prev) => [...prev, newField]);
        setAiHint("");
        setAddingField(null);
        toast.success(`Campo "${newField.name}" agregado`);
      } else {
        toast.error("Claude no encontró un selector para ese campo");
      }
    } catch (err) {
      toast.error(extractApiErrorMessage(err));
    }
  };

  // ── Step 3: Creation flow ────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!analyzeResult || !canCreate) return;
    setStep("creating");
    setCreateError(null);

    const editedRecipe = {
      ...analyzeResult.proposed_recipe,
      fields: editedFields,
    };

    try {
      const newSource = await scraperSourcesApi.create({
        name: analyzeResult.proposed_source.name,
        slug: analyzeResult.proposed_source.slug,
        base_url: analyzeResult.proposed_source.base_url,
        destination_profile: destProfile,
        fetch_mode: analyzeResult.detected_mode,
      });

      const newRecipe = await scraperSourcesApi.createRecipe(newSource.id, {
        recipe: editedRecipe,
      });

      const validation = await scraperSourcesApi.validate(newSource.id, {
        recipe_id: newRecipe.id,
        test_url: originalUrl,
      });

      let finalSource = newSource;
      if (validation.status === "passing") {
        finalSource = await scraperSourcesApi.activate(newSource.id, {
          recipe_id: newRecipe.id,
        });
      }

      await qc.invalidateQueries({ queryKey: scraperSourceKeys.all() });
      onSuccess?.(finalSource);
      toast.success(
        validation.status === "passing"
          ? "Scraper creado y activo"
          : "Scraper creado — activar manualmente cuando la validación pase",
      );
      onClose();
    } catch (err) {
      setStep("review");
      if (err instanceof ScraperSourcesApiError && err.status === 409) {
        setCreateError(
          `El slug "${analyzeResult.proposed_source.slug}" ya existe. ` +
            `Edita manualmente el nombre del source.`,
        );
      } else {
        setCreateError("Error al crear el scraper. Revisa los campos e intenta de nuevo.");
      }
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      {step === "url-form" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Crear scraper con AI</DialogTitle>
          </DialogHeader>
          <form onSubmit={urlForm.handleSubmit(handleAnalyze)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="wiz-url">URL del sitio *</Label>
              <Input
                id="wiz-url"
                placeholder="https://example.com/search?q=ball+valve"
                {...urlForm.register("url")}
              />
              {urlForm.formState.errors.url && (
                <p className="text-xs text-destructive">
                  {urlForm.formState.errors.url.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="wiz-ctx">Descripción (opcional)</Label>
              <Input
                id="wiz-ctx"
                placeholder="Ej: Sitio de proveedores industriales UAE"
                {...urlForm.register("context")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Destino</Label>
              <Select
                value={urlForm.watch("destination_profile")}
                onValueChange={(v) =>
                  urlForm.setValue("destination_profile", v as DestinationProfile)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="competitor_price">Precios competidor</SelectItem>
                  <SelectItem value="product_data">Datos de producto</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>
                Cancelar
              </Button>
              <Button type="submit" disabled={urlForm.formState.isSubmitting}>
                Analizar con AI →
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      )}

      {step === "analyzing" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Analizando sitio...</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            <p className="text-sm text-muted-foreground">Claude está analizando la página…</p>
          </div>
        </DialogContent>
      )}

      {step === "review" && analyzeResult && (
        <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-2 flex-wrap">
              <DialogTitle>Revisar propuesta</DialogTitle>
              <Badge variant="outline" className="text-xs">
                {analyzeResult.detected_mode}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {analyzeResult.proposed_source.name}
              </span>
              <Badge
                variant={canCreate ? "default" : "destructive"}
                className="ml-auto text-xs"
              >
                {REQUIRED_FIELD_NAMES.size - missingRequired.length}/{REQUIRED_FIELD_NAMES.size}{" "}
                requeridos
              </Badge>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {analyzeResult.detected_mode !== "static" && (
              <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>
                  Este sitio requiere navegador headless — el scraper solo funcionará
                  cuando el worker Playwright esté activo.
                </span>
              </div>
            )}

            {analyzeResult.warnings.length > 0 && (
              <div className="space-y-1">
                {analyzeResult.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    ⚠ {w}
                  </p>
                ))}
              </div>
            )}

            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Campos propuestos
              </p>
              {editedFields.map((f, i) => {
                const isRequired = REQUIRED_FIELD_NAMES.has(f.name);
                const confidence = analyzeResult.field_confidence[f.name] ?? 0;
                const isEditing = editingIndex === i;

                return (
                  <div key={i} className="border rounded-md">
                    <div className="flex items-center gap-2 p-2">
                      {confidence >= 0.7 ? (
                        <Check className="h-4 w-4 text-green-600 shrink-0" />
                      ) : confidence > 0 ? (
                        <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
                      ) : (
                        <X className="h-4 w-4 text-destructive shrink-0" />
                      )}
                      <span className="text-sm font-medium w-32 shrink-0">
                        {f.name}
                        {isRequired && <span className="text-destructive ml-0.5">*</span>}
                      </span>
                      <span className="text-xs text-muted-foreground truncate flex-1">
                        {f.selector} › {f.extract}
                      </span>
                      <div className="flex items-center gap-1 ml-auto">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={() =>
                            isEditing ? setEditingIndex(null) : handleEditField(i)
                          }
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                          onClick={() => handleRemoveField(i)}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>

                    {isEditing && (
                      <form
                        onSubmit={fieldForm.handleSubmit(handleSaveEdit)}
                        className="p-2 pt-0 border-t bg-muted/30 space-y-2"
                      >
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label className="text-xs">Campo</Label>
                            <Input className="h-7 text-xs" {...fieldForm.register("name")} />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Selector CSS</Label>
                            <Input className="h-7 text-xs" {...fieldForm.register("selector")} />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Extraer</Label>
                            <Input
                              className="h-7 text-xs"
                              placeholder="text / attr:href / attr:src"
                              {...fieldForm.register("extract")}
                            />
                          </div>
                          <div className="space-y-1">
                            <Label className="text-xs">Tipo</Label>
                            <Select
                              value={fieldForm.watch("type")}
                              onValueChange={(v) =>
                                fieldForm.setValue("type", v as FieldFormValues["type"])
                              }
                            >
                              <SelectTrigger className="h-7 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {(["str", "float", "int", "currency", "bool"] as const).map(
                                  (t) => (
                                    <SelectItem key={t} value={t} className="text-xs">
                                      {t}
                                    </SelectItem>
                                  ),
                                )}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        {(fieldForm.formState.errors.name ||
                          fieldForm.formState.errors.selector) && (
                          <p className="text-xs text-destructive">
                            {fieldForm.formState.errors.name?.message ??
                              fieldForm.formState.errors.selector?.message}
                          </p>
                        )}
                        <div className="flex gap-2 justify-end">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 text-xs"
                            type="button"
                            onClick={() => setEditingIndex(null)}
                          >
                            Cancelar
                          </Button>
                          <Button size="sm" className="h-6 text-xs" type="submit">
                            Guardar
                          </Button>
                        </div>
                      </form>
                    )}
                  </div>
                );
              })}

              {addingField === null ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full mt-1"
                  onClick={() => {
                    setAddingField("ai");
                    setEditingIndex(null);
                    fieldForm.reset();
                  }}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Agregar campo
                </Button>
              ) : (
                <div className="border rounded-md p-3 space-y-3 bg-muted/20">
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={addingField === "ai" ? "default" : "outline"}
                      className="h-7 text-xs"
                      type="button"
                      onClick={() => { setAddingField("ai"); fieldForm.reset(); }}
                    >
                      Buscar con AI
                    </Button>
                    <Button
                      size="sm"
                      variant={addingField === "manual" ? "default" : "outline"}
                      className="h-7 text-xs"
                      type="button"
                      onClick={() => { setAddingField("manual"); fieldForm.reset(); }}
                    >
                      Manual
                    </Button>
                  </div>

                  {addingField === "ai" && (
                    <div className="flex gap-2">
                      <Input
                        className="h-7 text-sm"
                        placeholder="Ej: la fecha de entrega estimada"
                        value={aiHint}
                        onChange={(e) => setAiHint(e.target.value)}
                      />
                      <Button
                        size="sm"
                        className="h-7 shrink-0"
                        onClick={handleFindWithAI}
                        disabled={!aiHint.trim() || analyzeUrl.isPending}
                      >
                        {analyzeUrl.isPending ? "Buscando…" : "Buscar →"}
                      </Button>
                    </div>
                  )}

                  {addingField === "manual" && (
                    <form
                      onSubmit={fieldForm.handleSubmit(handleAddManual)}
                      className="space-y-2"
                    >
                      <div className="grid grid-cols-2 gap-2">
                        <div className="space-y-1">
                          <Label className="text-xs">Campo</Label>
                          <Input className="h-7 text-xs" {...fieldForm.register("name")} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Selector CSS</Label>
                          <Input className="h-7 text-xs" {...fieldForm.register("selector")} />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Extraer</Label>
                          <Input
                            className="h-7 text-xs"
                            placeholder="text / attr:href"
                            {...fieldForm.register("extract")}
                          />
                        </div>
                        <div className="space-y-1">
                          <Label className="text-xs">Tipo</Label>
                          <Select
                            value={fieldForm.watch("type")}
                            onValueChange={(v) =>
                              fieldForm.setValue("type", v as FieldFormValues["type"])
                            }
                          >
                            <SelectTrigger className="h-7 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {(["str", "float", "int", "currency", "bool"] as const).map((t) => (
                                <SelectItem key={t} value={t} className="text-xs">
                                  {t}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="flex gap-2 justify-end">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 text-xs"
                          type="button"
                          onClick={() => setAddingField(null)}
                        >
                          Cancelar
                        </Button>
                        <Button size="sm" className="h-6 text-xs" type="submit">
                          Agregar
                        </Button>
                      </div>
                    </form>
                  )}

                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs text-muted-foreground"
                    onClick={() => setAddingField(null)}
                  >
                    Cancelar
                  </Button>
                </div>
              )}
            </div>

            {analyzeResult.preview_records.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Preview ({analyzeResult.preview_records.length} registros)
                </p>
                <div className="overflow-x-auto rounded-md border">
                  <table className="text-xs w-full">
                    <thead className="bg-muted/50">
                      <tr>
                        {editedFields.map((f) => (
                          <th
                            key={f.name}
                            className="px-2 py-1.5 text-left font-medium max-w-[120px] truncate"
                          >
                            {f.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {analyzeResult.preview_records.map((row, i) => (
                        <tr key={i} className="border-t">
                          {editedFields.map((f) => (
                            <td
                              key={f.name}
                              className="px-2 py-1.5 max-w-[120px] truncate text-muted-foreground"
                            >
                              {String(row[f.name] ?? "—")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {createError && <p className="text-sm text-destructive">{createError}</p>}
          </div>

          <DialogFooter className="border-t pt-3">
            <Button
              variant="outline"
              onClick={() => {
                setStep("url-form");
                setAnalyzeResult(null);
              }}
            >
              ← Volver
            </Button>
            <Button onClick={handleCreate} disabled={!canCreate}>
              Crear scraper →
            </Button>
          </DialogFooter>
        </DialogContent>
      )}

      {step === "creating" && (
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Creando scraper...</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            <p className="text-sm text-muted-foreground">
              Guardando fuente, receta y activando...
            </p>
          </div>
        </DialogContent>
      )}
    </Dialog>
  );
}
