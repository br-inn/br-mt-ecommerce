"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus } from "lucide-react";

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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import {
  FX_RATE_SOURCES,
  FxRatesApiError,
  type FXRateCreatePayload,
} from "@/lib/api/endpoints/fx-rates";
import { useCreateFxRateAdmin } from "@/lib/hooks/fx/use-fx-mutations";

interface Props {
  availableCodes: string[];
  triggerLabel?: string;
}

/**
 * `FxRateForm` — Dialog modal "Nueva tasa" (US-1A-05-03).
 *
 * - Validación zod en cliente: rate>0, par distinto, source enum.
 * - Mapea `error.code` del backend a mensaje localizado:
 *   - `fx_retroactive_not_allowed` → muestra checkbox `allow_retroactive`.
 *   - `fx_same_effective_from`     → instrucción de cambiar fecha.
 *   - `fx_rate_must_be_positive`   → validación inline.
 *   - `fx_invalid_currency`        → usa el listado activo.
 */
export function FxRateForm({ availableCodes, triggerLabel }: Props) {
  const t = useTranslations("fx_rates");
  const tCommon = useTranslations("common");
  const [open, setOpen] = React.useState(false);

  const schema = React.useMemo(
    () =>
      z
        .object({
          from_currency: z
            .string()
            .length(3, t("errors.currencyRequired")),
          to_currency: z.string().length(3, t("errors.currencyRequired")),
          rate: z.preprocess(
            (v) => (typeof v === "string" ? Number(v) : v),
            z.number().positive(t("errors.rateInvalid")),
          ),
          effective_from: z.string().min(1, t("errors.effectiveFromRequired")),
          source: z.enum(FX_RATE_SOURCES),
          allow_retroactive: z.boolean().default(false),
          reason: z.string().max(512).optional(),
        })
        .refine((v) => v.from_currency !== v.to_currency, {
          message: t("errors.samePair"),
          path: ["to_currency"],
        })
        .refine((v) => !v.allow_retroactive || (v.reason && v.reason.trim().length > 0), {
          message: t("errors.retroactiveReasonRequired"),
          path: ["reason"],
        }),
    [t],
  );

  type Values = z.infer<typeof schema>;

  const nowLocal = React.useMemo(() => {
    const d = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }, []);

  const form = useForm<Values>({
    resolver: zodResolver(schema) as Resolver<Values>,
    defaultValues: {
      from_currency: availableCodes[0] ?? "EUR",
      to_currency: availableCodes[1] ?? "AED",
      rate: 1,
      effective_from: nowLocal,
      source: "manual",
      allow_retroactive: false,
      reason: "",
    },
    mode: "onBlur",
  });

  const create = useCreateFxRateAdmin();

  const onSubmit = async (values: Values) => {
    const payload: FXRateCreatePayload = {
      from_currency: values.from_currency,
      to_currency: values.to_currency,
      rate: values.rate,
      effective_from: new Date(values.effective_from).toISOString(),
      source: values.source,
      allow_retroactive: values.allow_retroactive || undefined,
      reason: values.reason?.trim() || undefined,
    };
    try {
      await create.mutateAsync(payload);
      toast.success(t("feedback.created"));
      setOpen(false);
      form.reset({
        ...form.getValues(),
        rate: 1,
        reason: "",
        allow_retroactive: false,
      });
    } catch (err) {
      let message = t("errors.saveFailed");
      if (err instanceof FxRatesApiError) {
        if (err.code === "fx_retroactive_not_allowed") {
          message = t("errors.retroactiveBlocked");
          form.setValue("allow_retroactive", true);
        } else if (err.code === "fx_same_effective_from") {
          message = t("errors.sameEffectiveFrom");
        } else if (err.code === "fx_rate_must_be_positive") {
          message = t("errors.rateInvalid");
        } else if (err.code === "fx_invalid_currency") {
          message = t("errors.invalidCurrency");
        } else if (
          err.detail &&
          typeof err.detail === "object" &&
          "detail" in err.detail
        ) {
          const inner = (err.detail as { detail?: { title?: string } }).detail;
          if (inner?.title) message = inner.title;
        }
      }
      toast.error(message);
    }
  };

  const allowRetro = form.watch("allow_retroactive");

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4" /> {triggerLabel ?? t("newRateButton")}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{t("form.createTitle")}</DialogTitle>
          <DialogDescription>{t("form.createSubtitle")}</DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <Field
              label={t("fields.from")}
              error={form.formState.errors.from_currency?.message}
            >
              <Select
                value={form.watch("from_currency")}
                onValueChange={(v) =>
                  form.setValue("from_currency", v, { shouldValidate: true })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableCodes.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field
              label={t("fields.to")}
              error={form.formState.errors.to_currency?.message}
            >
              <Select
                value={form.watch("to_currency")}
                onValueChange={(v) =>
                  form.setValue("to_currency", v, { shouldValidate: true })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableCodes.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          <Field
            label={t("fields.rate")}
            error={form.formState.errors.rate?.message}
          >
            <Input
              type="number"
              step="0.0001"
              min={0}
              {...form.register("rate", { valueAsNumber: true })}
            />
          </Field>

          <Field
            label={t("fields.effective_from")}
            error={form.formState.errors.effective_from?.message}
          >
            <Input type="datetime-local" {...form.register("effective_from")} />
          </Field>

          <Field
            label={t("fields.source")}
            error={form.formState.errors.source?.message}
          >
            <Select
              value={form.watch("source")}
              onValueChange={(v) =>
                form.setValue("source", v as Values["source"], {
                  shouldValidate: true,
                })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FX_RATE_SOURCES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {t(`sources.${s}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <div className="rounded-md border bg-muted/30 p-3 space-y-2">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 rounded border-input"
                checked={allowRetro}
                onChange={(e) =>
                  form.setValue("allow_retroactive", e.target.checked, {
                    shouldValidate: true,
                  })
                }
              />
              <span>
                <strong className="block">
                  {t("fields.allowRetroactive")}
                </strong>
                <span className="text-xs text-muted-foreground">
                  {t("fields.allowRetroactiveHelp")}
                </span>
              </span>
            </label>
            {allowRetro ? (
              <Field
                label={t("fields.reason")}
                error={form.formState.errors.reason?.message}
              >
                <textarea
                  {...form.register("reason")}
                  rows={2}
                  maxLength={512}
                  placeholder={t("fields.reasonPlaceholder")}
                  className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </Field>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={create.isPending}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? tCommon("loading") : t("form.create")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
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
