"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
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
import {
  SUPPLIER_CURRENCIES,
  SuppliersApiError,
  type Supplier,
  type SupplierCreatePayload,
} from "@/lib/api/endpoints/suppliers";
import {
  useCreateSupplier,
  usePatchSupplier,
} from "@/lib/hooks/suppliers/use-suppliers";

interface Props {
  /** Si llega, modo edit. */
  initial?: Supplier;
  /** Callback opcional al finalizar (sheet/dialog use case). */
  onDone?: (supplier: Supplier) => void;
}

const buildSchema = (msgs: {
  codeRequired: string;
  codeFormat: string;
  nameMin: string;
  emailInvalid: string;
  leadTimeInvalid: string;
  currencyRequired: string;
}) =>
  z.object({
    code: z
      .string()
      .min(1, msgs.codeRequired)
      .regex(/^[A-Z0-9_-]+$/u, msgs.codeFormat),
    name: z.string().min(2, msgs.nameMin).max(256),
    contract_currency: z.string().length(3, msgs.currencyRequired),
    lead_time_days: z.preprocess(
      (v) =>
        v === "" || v === null || (typeof v === "number" && Number.isNaN(v))
          ? undefined
          : v,
      z.number().int().min(0, msgs.leadTimeInvalid).max(3650).optional(),
    ),
    contact_email: z
      .string()
      .email(msgs.emailInvalid)
      .or(z.literal(""))
      .optional(),
    contact_phone: z.string().max(64).optional(),
    payment_terms: z.string().max(256).optional(),
    notes: z.string().max(4096).optional(),
    active: z.boolean(),
  });

type FormValues = z.infer<ReturnType<typeof buildSchema>>;

function toCreatePayload(values: FormValues): SupplierCreatePayload {
  return {
    code: values.code,
    name: values.name,
    contract_currency: values.contract_currency,
    lead_time_days:
      typeof values.lead_time_days === "number" ? values.lead_time_days : null,
    contact_email: values.contact_email ? values.contact_email : null,
    contact_phone: values.contact_phone || null,
    payment_terms: values.payment_terms || null,
    notes: values.notes || null,
    active: values.active,
  };
}

/**
 * Form de alta/edición de proveedor — usa hooks TanStack Query.
 * Después del save, redirige a `/proveedores/{code}` (modo página) o llama
 * a `onDone` (modo modal/sheet).
 */
export function ProveedorFormClient({ initial, onDone }: Props) {
  const router = useRouter();
  const t = useTranslations("suppliers.form");
  const tFields = useTranslations("proveedores.fields");
  const tCommon = useTranslations("common");

  const schema = React.useMemo(
    () =>
      buildSchema({
        codeRequired: t("validation.codeRequired"),
        codeFormat: t("validation.codeFormat"),
        nameMin: t("validation.nameMin"),
        emailInvalid: t("validation.emailInvalid"),
        leadTimeInvalid: t("validation.leadTimeInvalid"),
        currencyRequired: t("validation.currencyRequired"),
      }),
    [t],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(schema) as Resolver<FormValues>,
    defaultValues: {
      code: initial?.code ?? "",
      name: initial?.name ?? "",
      contract_currency: initial?.contract_currency ?? "AED",
      lead_time_days: initial?.lead_time_days ?? undefined,
      contact_email: initial?.contact_email ?? "",
      contact_phone: initial?.contact_phone ?? "",
      payment_terms: initial?.payment_terms ?? "",
      notes: initial?.notes ?? "",
      active: initial?.active ?? true,
    },
    mode: "onBlur",
  });

  const createMut = useCreateSupplier();
  const patchMut = usePatchSupplier(initial?.code ?? "");

  const onSubmit = async (values: FormValues) => {
    try {
      const payload = toCreatePayload(values);
      const result = initial
        ? await patchMut.mutateAsync({
            name: payload.name,
            contract_currency: payload.contract_currency,
            lead_time_days: payload.lead_time_days,
            contact_email: payload.contact_email,
            contact_phone: payload.contact_phone,
            payment_terms: payload.payment_terms,
            notes: payload.notes,
            active: payload.active,
          })
        : await createMut.mutateAsync(payload);
      toast.success(initial ? t("updated") : t("created"));
      if (onDone) onDone(result);
      else router.push(`/proveedores/${encodeURIComponent(result.code)}`);
    } catch (err) {
      if (err instanceof SuppliersApiError) {
        if (err.status === 409) {
          form.setError("code", {
            type: "server",
            message: t("errors.duplicateCode"),
          });
          toast.error(t("errors.duplicateCode"));
          return;
        }
        const fields = err.fieldErrors();
        if (fields) {
          Object.entries(fields).forEach(([k, msg]) => {
            form.setError(k as Path<FormValues>, {
              type: "server",
              message: msg,
            });
          });
          toast.error(tCommon("error"));
          return;
        }
      }
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const isPending = createMut.isPending || patchMut.isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={form.handleSubmit(onSubmit)}
      noValidate
      data-testid="proveedor-form"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label={tFields("code")}
          error={form.formState.errors.code?.message}
        >
          <Input
            {...form.register("code")}
            placeholder="SUP_001"
            autoComplete="off"
            disabled={!!initial}
          />
        </Field>
        <Field
          label={tFields("name")}
          error={form.formState.errors.name?.message}
        >
          <Input {...form.register("name")} />
        </Field>
        <Field
          label={tFields("contract_currency")}
          error={form.formState.errors.contract_currency?.message}
        >
          <Select
            value={form.watch("contract_currency")}
            onValueChange={(v) =>
              form.setValue("contract_currency", v, { shouldValidate: true })
            }
          >
            <SelectTrigger aria-label={tFields("contract_currency")}>
              <SelectValue placeholder="—" />
            </SelectTrigger>
            <SelectContent>
              {SUPPLIER_CURRENCIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field
          label={tFields("lead_time_days")}
          error={form.formState.errors.lead_time_days?.message}
        >
          <Input
            type="number"
            min={0}
            step={1}
            {...form.register("lead_time_days", { valueAsNumber: true })}
          />
        </Field>
        <Field
          label={tFields("contact_email")}
          error={form.formState.errors.contact_email?.message}
        >
          <Input
            type="email"
            {...form.register("contact_email")}
            autoComplete="email"
          />
        </Field>
        <Field label={tFields("contact_phone")}>
          <Input type="tel" {...form.register("contact_phone")} />
        </Field>
        <Field label={tFields("payment_terms_days")}>
          <Input {...form.register("payment_terms")} placeholder="Net 30" />
        </Field>
        <div className="flex items-center gap-3 pt-6">
          <input
            id="proveedor-active"
            type="checkbox"
            className="h-4 w-4 rounded border-input"
            {...form.register("active")}
          />
          <Label htmlFor="proveedor-active">{tFields("active")}</Label>
        </div>
      </div>

      <Field label={tFields("notes")}>
        <textarea
          {...form.register("notes")}
          rows={3}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </Field>

      <div className="flex items-center justify-end gap-2 pt-2">
        {onDone ? (
          <Button
            type="button"
            variant="ghost"
            onClick={() => onDone(initial as Supplier)}
          >
            {tCommon("cancel")}
          </Button>
        ) : null}
        <Button type="submit" disabled={isPending} data-testid="proveedor-submit">
          {isPending
            ? tCommon("loading")
            : initial
              ? t("submitEdit")
              : t("submitCreate")}
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
