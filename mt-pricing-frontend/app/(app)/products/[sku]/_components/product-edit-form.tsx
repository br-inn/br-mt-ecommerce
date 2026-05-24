"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm, type Path, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

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
import { useUpdateProduct } from "@/lib/hooks/products/use-product-mutations";
import {
  PRODUCT_FAMILIES,
  ProductsApiError,
  type Product,
  type ProductUpdatePayload,
} from "@/lib/api/endpoints/products";
import { getProductName } from "@/lib/utils/product-display";

interface Props {
  product: Product;
  onCancel: () => void;
  onSaved?: () => void;
}

const buildSchema = (msgs: { weightInvalid: string }) =>
  z.object({
    family: z.enum(PRODUCT_FAMILIES),
    type: z.string().optional(),
    dn: z.string().optional(),
    pn: z.string().optional(),
    material: z.string().optional(),
    connection: z.string().optional(),
    weight_kg: z.preprocess(
      (v) =>
        v === "" || v === null || (typeof v === "number" && Number.isNaN(v))
          ? undefined
          : v,
      z.number().positive(msgs.weightInvalid).optional(),
    ),
  });

type FormValues = z.infer<ReturnType<typeof buildSchema>>;

/**
 * Fase B: `name_en` / `description_en` ya no se editan desde aquí — viven en
 * `product_translations(lang='en')` y se editan en el tab "Traducciones".
 */
function toPayload(values: FormValues): ProductUpdatePayload {
  return {
    family: values.family,
    type: values.type || null,
    dn: values.dn || null,
    pn: values.pn || null,
    material: values.material || null,
    connection: values.connection || null,
    weight_kg:
      typeof values.weight_kg === "number" ? values.weight_kg : null,
  };
}

/**
 * Form inline para editar la "Identidad" del SKU dentro del tab Ficha técnica
 * (US-1A-02-04-S2). Optimistic update via TanStack mutate; maneja 412 con
 * toast "Conflicto, recarga".
 */
export function ProductEditForm({ product, onCancel, onSaved }: Props) {
  const t = useTranslations("catalog.edit");
  const tFields = useTranslations("catalog.product.fields");
  const tCommon = useTranslations("common");

  const schema = React.useMemo(
    () =>
      buildSchema({
        weightInvalid: t("validation.weightInvalid"),
      }),
    [t],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as Resolver<FormValues>,
    defaultValues: {
      family: (product.family as (typeof PRODUCT_FAMILIES)[number]) ?? PRODUCT_FAMILIES[0],
      type: product.type ?? "",
      dn: product.dn ?? "",
      pn: product.pn ?? "",
      material: product.material ?? "",
      connection: product.connection ?? "",
      weight_kg: product.weight_kg ?? undefined,
    },
    mode: "onBlur",
  });

  const update = useUpdateProduct(product.sku);

  const onSubmit = async (values: FormValues) => {
    try {
      await update.mutateAsync(toPayload(values));
      toast.success(t("success"));
      onSaved?.();
    } catch (err) {
      if (err instanceof ProductsApiError) {
        if (err.status === 412) {
          toast.error(t("conflict"));
          return;
        }
        const fields = err.fieldErrors();
        if (fields) {
          Object.entries(fields).forEach(([k, msg]) => {
            form.setError(k as Path<FormValues>, { type: "server", message: msg });
          });
          toast.error(tCommon("error"));
          return;
        }
      }
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(onSubmit)}
      noValidate
      data-testid="product-edit-form"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={tFields("sku")}>
          <Input value={product.sku} disabled className="bg-muted/50" />
        </Field>
        <Field label={tFields("name_en")}>
          <Input
            value={getProductName(product)}
            disabled
            className="bg-muted/50"
          />
        </Field>
        <Field label={tFields("family")}>
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
        <Field label={tFields("type")}>
          <Input {...form.register("type")} />
        </Field>
        <Field label={tFields("dn")}>
          <Input {...form.register("dn")} />
        </Field>
        <Field label={tFields("pn")}>
          <Input {...form.register("pn")} />
        </Field>
        <Field label={tFields("material")}>
          <Input {...form.register("material")} />
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
      </div>

      {/*
        Fase B: `description_en` ya no se edita aquí. Vive en
        `product_translations(lang='en')` y se gestiona desde el tab
        "Traducciones".
      */}

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {tCommon("cancel")}
        </Button>
        <Button
          type="submit"
          disabled={update.isPending}
          data-testid="product-edit-submit"
        >
          {update.isPending ? t("saving") : t("submit")}
        </Button>
      </div>
    </form>
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
