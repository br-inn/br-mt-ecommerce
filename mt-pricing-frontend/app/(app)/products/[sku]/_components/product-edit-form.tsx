"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm, type Path } from "react-hook-form";
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

interface Props {
  product: Product;
  onCancel: () => void;
  onSaved?: () => void;
}

const buildSchema = (msgs: {
  nameMin: string;
  weightInvalid: string;
}) =>
  z.object({
    name_en: z.string().min(3, msgs.nameMin),
    description_en: z.string().optional(),
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

function toPayload(values: FormValues): ProductUpdatePayload {
  return {
    name_en: values.name_en,
    description_en: values.description_en || null,
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
        nameMin: t("validation.nameMin"),
        weightInvalid: t("validation.weightInvalid"),
      }),
    [t],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name_en: product.name_en,
      description_en: product.description_en ?? "",
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
        <Field
          label={tFields("name_en")}
          error={form.formState.errors.name_en?.message}
        >
          <Input {...form.register("name_en")} />
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

      <Field label={tFields("description_en")}>
        <textarea
          {...form.register("description_en")}
          rows={3}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </Field>

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
