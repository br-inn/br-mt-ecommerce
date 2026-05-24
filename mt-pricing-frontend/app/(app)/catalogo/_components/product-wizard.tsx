"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm, type Path, type UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils/cn";
import { useFormStep } from "@/lib/hooks/use-form-step";
import { useQuery } from "@tanstack/react-query";
import { divisionsApi } from "@/lib/api/endpoints/divisions";
import { materialsApi } from "@/lib/api/endpoints/materials";
import { seriesApi } from "@/lib/api/endpoints/series";
import {
  useCreateProduct,
  useUpdateProduct,
} from "@/lib/hooks/products/use-product-mutations";
import {
  PRODUCT_FAMILIES,
  ProductsApiError,
  type Product,
  type ProductCreatePayload,
  type ProductUpdatePayload,
} from "@/lib/api/endpoints/products";
import {
  isPermissiveDefaultSchema,
  useSpecsSchema,
} from "@/lib/api/endpoints/specs";
import { DynamicSpecsForm } from "./dynamic-specs-form";

const familySchema = z.enum(PRODUCT_FAMILIES);

const eanSchema = z
  .string()
  .regex(/^\d{12,14}$/u)
  .or(z.literal(""))
  .optional();

const createSchema = (msgs: {
  skuRequired: string;
  skuFormat: string;
  nameRequired: string;
  nameMin: string;
  familyRequired: string;
  weightInvalid: string;
  moqInvalid: string;
  qtyInvalid: string;
  eanFormat: string;
}) =>
  z.object({
    sku: z
      .string()
      .min(1, msgs.skuRequired)
      .regex(/^[A-Z0-9_-]+$/u, msgs.skuFormat),
    name_en: z.string().min(3, msgs.nameMin),
    family: familySchema,
    active: z.boolean(),

    dn: z.string().optional(),
    pn: z.string().optional(),
    material: z.string().optional(),
    type: z.string().optional(),
    connection: z.string().optional(),
    weight_kg: z
      .preprocess(
        (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
        z.number().positive(msgs.weightInvalid).optional(),
      ),
    length: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
    width: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),
    height: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),

    qty_x_box: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().int().positive(msgs.qtyInvalid).optional(),
    ),
    moq: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().int().positive(msgs.moqInvalid).optional(),
    ),
    ean_unit: eanSchema,
    ean_box: eanSchema,

    hs_code: z.string().optional(),
    origin_country: z.string().optional(),
    net_weight_kg: z.preprocess(
      (v) => (v === "" || v === null || (typeof v === "number" && Number.isNaN(v)) ? undefined : v),
      z.number().positive().optional(),
    ),

    // Stage 3 (Wave 11) — taxonomía
    series_id: z.string().uuid().or(z.literal("")).optional(),
    material_id: z.string().uuid().or(z.literal("")).optional(),
    division_codes: z.array(z.string()).optional(),
  });

type WizardForm = z.infer<ReturnType<typeof createSchema>>;

const STEP_FIELDS: Path<WizardForm>[][] = [
  ["sku", "name_en", "family", "active"],
  // Step 1: dynamic specs (validated by backend, no local fields).
  [],
  [
    "dn", "pn", "material", "type", "connection", "weight_kg", "length", "width", "height",
    // Stage 3 (Wave 11) — taxonomía Stage 3 vive con el resto de metadatos físicos.
    "series_id", "material_id", "division_codes",
  ],
  ["qty_x_box", "moq", "ean_unit", "ean_box", "hs_code", "origin_country", "net_weight_kg"],
  [],
];

function toNumberOrNull(v: unknown): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim().length > 0) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function buildPayload(
  values: WizardForm,
  specs: Record<string, unknown> | null,
): ProductCreatePayload {
  const dimensions =
    values.length || values.width || values.height
      ? {
          length: toNumberOrNull(values.length ?? null),
          width: toNumberOrNull(values.width ?? null),
          height: toNumberOrNull(values.height ?? null),
          unit: "mm" as const,
        }
      : null;
  const packaging =
    values.qty_x_box || values.moq || values.ean_unit || values.ean_box
      ? {
          qty_x_box: toNumberOrNull(values.qty_x_box ?? null),
          moq: toNumberOrNull(values.moq ?? null),
          ean_unit: values.ean_unit ? values.ean_unit : null,
          ean_box: values.ean_box ? values.ean_box : null,
        }
      : null;
  const intrastat =
    values.hs_code || values.origin_country || values.net_weight_kg
      ? {
          hs_code: values.hs_code ?? null,
          origin_country: values.origin_country ?? null,
          net_weight_kg: toNumberOrNull(values.net_weight_kg ?? null),
        }
      : null;

  const specsPayload =
    specs && Object.keys(specs).length > 0 ? specs : null;

  // Stage 3 (Wave 11) — taxonomy fields (only included when set).
  const stage3: Partial<ProductCreatePayload> = {};
  if (values.series_id) stage3.series_id = values.series_id as string;
  if (values.material_id) stage3.material_id = values.material_id as string;
  if (values.division_codes && values.division_codes.length > 0) {
    stage3.division_codes = values.division_codes;
  }

  return {
    sku: values.sku,
    name_en: values.name_en,
    family: values.family,
    active: values.active,
    dn: values.dn || null,
    pn: values.pn || null,
    material: values.material || null,
    type: values.type || null,
    connection: values.connection || null,
    weight_kg: toNumberOrNull(values.weight_kg ?? null),
    dimensions,
    packaging,
    intrastat,
    specs: specsPayload,
    ...stage3,
  };
}

/**
 * Mapea un Product (backend) a los valores de formulario del wizard.
 * Aplana `dimensions/packaging/intrastat` en campos planos esperados por el form.
 */
function productToFormValues(product: Product): WizardForm {
  const family = (
    PRODUCT_FAMILIES as readonly string[]
  ).includes(product.family ?? "")
    ? (product.family as (typeof PRODUCT_FAMILIES)[number])
    : (PRODUCT_FAMILIES[0] as (typeof PRODUCT_FAMILIES)[number]);

  const out: WizardForm = {
    sku: product.sku,
    name_en: product.name_en,
    family,
    active: product.active,
    dn: product.dn ?? "",
    pn: product.pn ?? "",
    material: product.material?.code ?? "",
    type: product.type ?? "",
    connection: product.connection ?? "",
    ean_unit: product.packaging?.ean_unit ?? "",
    ean_box: product.packaging?.ean_box ?? "",
    hs_code: product.intrastat?.hs_code ?? "",
    origin_country: product.intrastat?.origin_country ?? "",
  };
  if (product.weight_kg != null) out.weight_kg = product.weight_kg;
  if (product.dimensions?.length != null) out.length = product.dimensions.length;
  if (product.dimensions?.width != null) out.width = product.dimensions.width;
  if (product.dimensions?.height != null) out.height = product.dimensions.height;
  if (product.packaging?.qty_x_box != null)
    out.qty_x_box = product.packaging.qty_x_box;
  if (product.packaging?.moq != null) out.moq = product.packaging.moq;
  if (product.intrastat?.net_weight_kg != null)
    out.net_weight_kg = product.intrastat.net_weight_kg;
  return out;
}

interface CreateProps {
  mode?: "create";
  defaultValues?: Partial<WizardForm>;
}

interface EditProps {
  mode: "edit";
  product: Product;
}

type Props = CreateProps | EditProps;

export function ProductWizard(props: Props) {
  const router = useRouter();
  const t = useTranslations("catalog.create");
  const tEdit = useTranslations("catalog.edit");
  const tFields = useTranslations("catalog.product.fields");
  const tCommon = useTranslations("common");

  const isEdit = props.mode === "edit";
  const editProduct = isEdit ? props.product : null;
  const createDefaults = isEdit ? null : props.defaultValues;
  const initialValues = React.useMemo<Partial<WizardForm>>(() => {
    if (editProduct) return productToFormValues(editProduct);
    return createDefaults ?? {};
  }, [editProduct, createDefaults]);

  const schema = React.useMemo(
    () =>
      createSchema({
        skuRequired: t("validation.skuRequired"),
        skuFormat: t("validation.skuFormat"),
        nameRequired: t("validation.nameRequired"),
        nameMin: t("validation.nameMin"),
        familyRequired: t("validation.familyRequired"),
        weightInvalid: t("validation.weightInvalid"),
        moqInvalid: t("validation.moqInvalid"),
        qtyInvalid: t("validation.qtyInvalid"),
        eanFormat: t("validation.eanFormat"),
      }),
    [t],
  );

  const form = useForm<WizardForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      sku: "",
      name_en: "",
      family: PRODUCT_FAMILIES[0] as (typeof PRODUCT_FAMILIES)[number],
      active: true,
      ...initialValues,
    },
    mode: "onBlur",
  });

  // Edit-mode: inyectar valores cuando el product cambie (carga async).
  // `initialValues` ya está memoizado por SKU del producto, por lo que el
  // reset solo dispara cuando cambia la identidad del producto cargado.
  React.useEffect(() => {
    if (isEdit) {
      form.reset(initialValues as WizardForm);
    }
  }, [isEdit, initialValues, form]);

  // Specs JSONB state (Stage 4): family/subfamily-specific structured attributes.
  // Validation happens server-side; we only collect the value here.
  const family = form.watch("family");
  const specsQuery = useSpecsSchema(family ?? undefined);
  const specsSchema = specsQuery.data;
  const isPermissiveSpecs = isPermissiveDefaultSchema(specsSchema);

  const [specs, setSpecs] = React.useState<Record<string, unknown>>({});
  const [specsErrors, setSpecsErrors] = React.useState<Record<string, string>>({});

  // Reset specs when family changes (different schema).
  const prevFamilyRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (prevFamilyRef.current !== null && prevFamilyRef.current !== family) {
      setSpecs({});
      setSpecsErrors({});
    }
    prevFamilyRef.current = family;
  }, [family]);

  const { step, isFirst, isLast, next, prev, goTo } = useFormStep<WizardForm>({
    total: 5,
    fieldsByStep: STEP_FIELDS,
    form,
  });

  // If schema is permissive (`_default` catch-all), skip the dynamic specs step
  // forward when the user advances and backward when stepping back.
  const handleNext = React.useCallback(async () => {
    const ok = await next();
    if (ok && step === 0 && isPermissiveSpecs) {
      goTo(2);
    }
    return ok;
  }, [next, step, isPermissiveSpecs, goTo]);

  const handlePrev = React.useCallback(() => {
    if (step === 2 && isPermissiveSpecs) {
      goTo(0);
      return;
    }
    prev();
  }, [step, isPermissiveSpecs, goTo, prev]);

  const createMut = useCreateProduct();
  const updateMut = useUpdateProduct(
    isEdit ? (props as EditProps).product.sku : "",
  );
  const submitting = isEdit ? updateMut.isPending : createMut.isPending;

  const onFinalSubmit = async (values: WizardForm) => {
    const payload = buildPayload(values, specs);
    try {
      if (isEdit) {
        const editProps = props as EditProps;
        // En edición el SKU es read-only; no lo enviamos.
        const { sku: _omit, ...rest } = payload;
        await updateMut.mutateAsync(rest as ProductUpdatePayload);
        toast.success(tEdit("success"));
        router.push(`/catalogo/${editProps.product.sku}`);
      } else {
        const created = await createMut.mutateAsync(payload);
        toast.success(t("success"));
        router.push(`/catalogo/${created.sku}`);
      }
    } catch (err) {
      if (err instanceof ProductsApiError) {
        const fields = err.fieldErrors();
        if (fields) {
          // Split errors: those rooted at "specs.*" go to DynamicSpecsForm;
          // the rest map to react-hook-form fields.
          const nextSpecsErrors: Record<string, string> = {};
          let hasSpecsError = false;
          Object.entries(fields).forEach(([k, msg]) => {
            if (k === "specs" || k.startsWith("specs.")) {
              const path = k === "specs" ? "" : k.slice("specs.".length);
              if (path) nextSpecsErrors[path] = msg;
              hasSpecsError = true;
            } else {
              form.setError(k as Path<WizardForm>, { type: "server", message: msg });
            }
          });
          if (hasSpecsError) {
            setSpecsErrors(nextSpecsErrors);
            // Bring the user back to the specs step so they can fix it.
            if (!isPermissiveSpecs) goTo(1);
          }
          toast.error(tCommon("error"));
          return;
        }
      }
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const allStepTitles = [
    t("step1"),
    t("specsStep"),
    t("step2"),
    t("step3"),
    t("step4"),
  ];
  const allStepDescs = [
    t("step1Description"),
    t("specsStepDescription"),
    t("step2Description"),
    t("step3Description"),
    t("step4Description"),
  ];
  // When the schema is permissive, hide the dynamic specs step from the
  // visible stepper (we still keep it in the underlying state machine for
  // simpler indexing). The skip is handled in handleNext/handlePrev.
  const stepTitles = isPermissiveSpecs
    ? allStepTitles.filter((_, i) => i !== 1)
    : allStepTitles;
  // For the stepper highlight, map the underlying step (0..4) into the
  // visible step index (0..3 when permissive, 0..4 otherwise).
  const visibleStep = isPermissiveSpecs && step >= 1 ? step - 1 : step;

  return (
    <form
      className="space-y-6"
      onSubmit={form.handleSubmit(onFinalSubmit)}
      noValidate
      data-testid="product-wizard"
    >
      <Stepper currentStep={visibleStep} stepTitles={stepTitles} />

      <Card>
        <CardHeader>
          <CardTitle>{allStepTitles[step]}</CardTitle>
          <CardDescription>{allStepDescs[step]}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 0 ? (
            <>
              <Field label={tFields("sku")} error={form.formState.errors.sku?.message}>
                <Input
                  {...form.register("sku")}
                  placeholder="VAL-DN50-PN16"
                  autoComplete="off"
                  readOnly={isEdit}
                  className={isEdit ? "bg-muted" : undefined}
                />
              </Field>
              <Field label={tFields("name_en")} error={form.formState.errors.name_en?.message}>
                <Input {...form.register("name_en")} />
              </Field>
              <Field label={tFields("family")} error={form.formState.errors.family?.message}>
                <Select
                  value={form.watch("family")}
                  onValueChange={(v) =>
                    form.setValue("family", v as (typeof PRODUCT_FAMILIES)[number], {
                      shouldValidate: true,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PRODUCT_FAMILIES.map((f) => (
                      <SelectItem key={f} value={f} className="capitalize">
                        {f}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <div className="flex items-center gap-3">
                <input
                  id="wizard-active"
                  type="checkbox"
                  className="h-4 w-4 rounded border-input"
                  {...form.register("active")}
                />
                <Label htmlFor="wizard-active">{tFields("active")}</Label>
              </div>
            </>
          ) : null}

          {step === 1 ? (
            <div className="space-y-4">
              {!family ? (
                <p className="text-sm text-muted-foreground">
                  Selecciona una familia en el paso anterior para ver los
                  atributos técnicos.
                </p>
              ) : specsQuery.isLoading ? (
                <div
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                  data-testid="specs-loading"
                >
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-muted-foreground/40 border-t-transparent" />
                  {t("specsLoading")}
                </div>
              ) : specsQuery.isError || !specsSchema ? (
                <p className="text-sm text-destructive" role="alert">
                  {t("specsError")}
                </p>
              ) : (
                <DynamicSpecsForm
                  schema={specsSchema}
                  value={specs}
                  onChange={(v) => {
                    setSpecs(v);
                    // Clear errors for fields that the user just edited.
                    if (Object.keys(specsErrors).length > 0) {
                      setSpecsErrors({});
                    }
                  }}
                  errors={specsErrors}
                />
              )}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={tFields("dn")}>
                <Input {...form.register("dn")} />
              </Field>
              <Field label={tFields("pn")}>
                <Input {...form.register("pn")} />
              </Field>
              <Field label={tFields("material")}>
                <Input {...form.register("material")} />
              </Field>
              <Field label={tFields("type")}>
                <Input {...form.register("type")} />
              </Field>
              <Field label={tFields("connection")}>
                <Input {...form.register("connection")} />
              </Field>
              <Field
                label={tFields("weight_kg")}
                error={form.formState.errors.weight_kg?.message}
              >
                <Input
                  type="number"
                  step="0.001"
                  {...form.register("weight_kg", { valueAsNumber: true })}
                />
              </Field>
              <Field label={tFields("length")}>
                <Input
                  type="number"
                  step="0.1"
                  {...form.register("length", { valueAsNumber: true })}
                />
              </Field>
              <Field label={tFields("width")}>
                <Input
                  type="number"
                  step="0.1"
                  {...form.register("width", { valueAsNumber: true })}
                />
              </Field>
              <Field label={tFields("height")}>
                <Input
                  type="number"
                  step="0.1"
                  {...form.register("height", { valueAsNumber: true })}
                />
              </Field>

              {/* Stage 3 (Wave 11) — taxonomía: serie, material curado, divisiones */}
              <div className="col-span-full mt-3 rounded-md border bg-muted/30 p-3">
                <h4 className="mb-3 text-sm font-semibold">Taxonomía Stage 3</h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Stage3SeriesPicker form={form} />
                  <Stage3MaterialPicker form={form} />
                  <div className="col-span-full">
                    <Stage3DivisionsPicker form={form} />
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label={tFields("qty_x_box")}
                error={form.formState.errors.qty_x_box?.message}
              >
                <Input
                  type="number"
                  step="1"
                  {...form.register("qty_x_box", { valueAsNumber: true })}
                />
              </Field>
              <Field label={tFields("moq")} error={form.formState.errors.moq?.message}>
                <Input
                  type="number"
                  step="1"
                  {...form.register("moq", { valueAsNumber: true })}
                />
              </Field>
              <Field
                label={tFields("ean_unit")}
                error={form.formState.errors.ean_unit?.message}
              >
                <Input {...form.register("ean_unit")} placeholder="123456789012" />
              </Field>
              <Field
                label={tFields("ean_box")}
                error={form.formState.errors.ean_box?.message}
              >
                <Input {...form.register("ean_box")} />
              </Field>
              <Separator className="sm:col-span-2" />
              <Field label={tFields("hs_code")}>
                <Input {...form.register("hs_code")} />
              </Field>
              <Field label={tFields("origin_country")}>
                <Input {...form.register("origin_country")} placeholder="ES" />
              </Field>
              <Field
                label={tFields("net_weight_kg")}
                error={form.formState.errors.net_weight_kg?.message}
              >
                <Input
                  type="number"
                  step="0.001"
                  {...form.register("net_weight_kg", { valueAsNumber: true })}
                />
              </Field>
            </div>
          ) : null}

          {step === 4 ? (
            isEdit ? (
              <DiffSummary
                form={form}
                initial={initialValues as WizardForm}
                tFields={tFields}
              />
            ) : (
              <ConfirmationSummary form={form} tFields={tFields} />
            )
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button type="button" variant="ghost" onClick={handlePrev} disabled={isFirst}>
          <ChevronLeft className="h-4 w-4" /> {tCommon("previous")}
        </Button>
        {!isLast ? (
          <Button
            type="button"
            onClick={() => {
              void handleNext();
            }}
          >
            {tCommon("next")} <ChevronRight className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="submit" disabled={submitting}>
            {submitting
              ? isEdit
                ? tEdit("saving")
                : t("creating")
              : isEdit
                ? tEdit("submit")
                : t("submit")}
            <Check className="h-4 w-4" />
          </Button>
        )}
      </div>
    </form>
  );
}

function Stepper({
  currentStep,
  stepTitles,
}: {
  currentStep: number;
  stepTitles: string[];
}) {
  return (
    <ol
      className="flex items-center gap-2 text-sm"
      role="list"
      aria-label="Stepper"
    >
      {stepTitles.map((title, idx) => {
        const done = idx < currentStep;
        const current = idx === currentStep;
        return (
          <li key={title} className="flex flex-1 items-center gap-2">
            <span
              aria-current={current ? "step" : undefined}
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ring-2 ring-offset-2 ring-offset-background",
                done
                  ? "bg-primary text-primary-foreground ring-primary"
                  : current
                    ? "bg-primary/10 text-primary ring-primary"
                    : "bg-muted text-muted-foreground ring-transparent",
              )}
            >
              {done ? <Check className="h-3 w-3" /> : idx + 1}
            </span>
            <span
              className={cn(
                "hidden text-xs font-medium md:inline",
                current ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {title}
            </span>
            {idx < stepTitles.length - 1 ? (
              <span className="h-px flex-1 bg-border" aria-hidden />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

// ----------------------------------------------------------------------------
// Stage 3 (Wave 11) — wizard pickers para taxonomía
// ----------------------------------------------------------------------------

function Stage3SeriesPicker({ form }: { form: UseFormReturn<WizardForm> }) {
  const seriesQ = useQuery({
    queryKey: ["wizard", "series", "list"],
    queryFn: () => seriesApi.listPublic({}),
    staleTime: 5 * 60_000,
  });
  const value = form.watch("series_id") ?? "";
  return (
    <Field label="Serie">
      <select
        value={typeof value === "string" ? value : ""}
        onChange={(e) =>
          form.setValue("series_id", e.target.value, { shouldDirty: true })
        }
        className="flex h-9 w-full rounded-md border bg-background px-3 text-sm"
      >
        <option value="">— sin serie —</option>
        {(seriesQ.data ?? []).map((s) => (
          <option key={s.id} value={s.id}>
            {s.name_en} ({s.code})
          </option>
        ))}
      </select>
    </Field>
  );
}

function Stage3MaterialPicker({ form }: { form: UseFormReturn<WizardForm> }) {
  const materialsQ = useQuery({
    queryKey: ["wizard", "materials", "list"],
    queryFn: () => materialsApi.listPublic(),
    staleTime: 5 * 60_000,
  });
  const value = form.watch("material_id") ?? "";
  return (
    <Field label="Material curado">
      <select
        value={typeof value === "string" ? value : ""}
        onChange={(e) =>
          form.setValue("material_id", e.target.value, { shouldDirty: true })
        }
        className="flex h-9 w-full rounded-md border bg-background px-3 text-sm"
      >
        <option value="">— sin material curado —</option>
        {(materialsQ.data ?? []).map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </select>
    </Field>
  );
}

function Stage3DivisionsPicker({ form }: { form: UseFormReturn<WizardForm> }) {
  const divisionsQ = useQuery({
    queryKey: ["wizard", "divisions", "list"],
    queryFn: () => divisionsApi.listPublic(),
    staleTime: 5 * 60_000,
  });
  const selected = (form.watch("division_codes") ?? []) as string[];
  const toggle = (code: string) => {
    const next = selected.includes(code)
      ? selected.filter((c) => c !== code)
      : [...selected, code];
    form.setValue("division_codes", next, { shouldDirty: true });
  };
  return (
    <Field label="Divisiones (M:N)">
      <div className="flex flex-wrap gap-2">
        {(divisionsQ.data ?? []).map((d) => {
          const isOn = selected.includes(d.code);
          return (
            <button
              key={d.code}
              type="button"
              onClick={() => toggle(d.code)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                isOn
                  ? "bg-primary text-primary-foreground"
                  : "bg-background hover:bg-accent",
              )}
            >
              {d.name}
            </button>
          );
        })}
      </div>
    </Field>
  );
}

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string | undefined;
  children: React.ReactNode;
}) {
  const id = React.useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div id={id}>{children}</div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function ConfirmationSummary({
  form,
  tFields,
}: {
  form: UseFormReturn<WizardForm>;
  tFields: (key: string) => string;
}) {
  const v = form.watch();
  const rows: [string, React.ReactNode][] = [
    [tFields("sku"), v.sku || "—"],
    [tFields("name_en"), v.name_en || "—"],
    [tFields("family"), v.family],
    [tFields("active"), v.active ? "Yes" : "No"],
    [tFields("dn"), v.dn || "—"],
    [tFields("pn"), v.pn || "—"],
    [tFields("material"), v.material || "—"],
    [tFields("weight_kg"), v.weight_kg ?? "—"],
    [tFields("qty_x_box"), v.qty_x_box ?? "—"],
    [tFields("moq"), v.moq ?? "—"],
    [tFields("hs_code"), v.hs_code || "—"],
    [tFields("origin_country"), v.origin_country || "—"],
  ];
  return (
    <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
      {rows.map(([k, val]) => (
        <div key={k} className="flex flex-col gap-0.5 rounded-md border bg-muted/30 p-3">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">{k}</dt>
          <dd className="font-medium">{val}</dd>
        </div>
      ))}
    </dl>
  );
}

function fmtValue(v: unknown): string {
  if (v === undefined || v === null || v === "") return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

function DiffSummary({
  form,
  initial,
  tFields,
}: {
  form: UseFormReturn<WizardForm>;
  initial: WizardForm;
  tFields: (key: string) => string;
}) {
  const tEdit = useTranslations("catalog.edit");
  const current = form.watch();

  type Key = keyof WizardForm;
  const tracked: Key[] = [
    "name_en",
    "family",
    "active",
    "dn",
    "pn",
    "material",
    "type",
    "connection",
    "weight_kg",
    "length",
    "width",
    "height",
    "qty_x_box",
    "moq",
    "ean_unit",
    "ean_box",
    "hs_code",
    "origin_country",
    "net_weight_kg",
  ];

  const changes = tracked.flatMap<{ key: Key; from: unknown; to: unknown }>(
    (k) => {
      const from = initial[k];
      const to = current[k];
      const isEq =
        (from ?? "") === (to ?? "") ||
        (from === undefined && to === undefined) ||
        (typeof from === "number" &&
          typeof to === "number" &&
          Number(from) === Number(to));
      return isEq ? [] : [{ key: k, from, to }];
    },
  );

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {tEdit("diffSubtitle", { count: changes.length })}
      </p>
      {changes.length === 0 ? (
        <p className="rounded-md border border-dashed bg-muted/30 p-4 text-center text-sm text-muted-foreground">
          {tEdit("noChanges")}
        </p>
      ) : (
        <ul className="divide-y rounded-md border">
          {changes.map((c) => (
            <li
              key={String(c.key)}
              className="grid grid-cols-1 gap-1 p-3 text-sm sm:grid-cols-[200px_1fr]"
            >
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                {tFields(String(c.key))}
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground line-through">
                  {fmtValue(c.from)}
                </span>
                <span className="text-muted-foreground">→</span>
                <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-primary">
                  {fmtValue(c.to)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
