"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  FX_SOURCES,
  type FXRateCreatePayload,
} from "@/lib/api/endpoints/fx";
import {
  useCreateFxRate,
  useCurrencies,
  useFxRates,
} from "@/lib/hooks/fx/use-fx";

const ALL = "__all__";

export function DivisasClient() {
  return (
    <div className="space-y-8">
      <CurrenciesSection />
      <RatesSection />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Currencies (read-only)
// ---------------------------------------------------------------------------
function CurrenciesSection() {
  const t = useTranslations("fx");
  const tCols = useTranslations("fx.columns");
  const { data, isLoading, isError } = useCurrencies();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("currenciesTitle")}</CardTitle>
        <CardDescription>{t("currenciesSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : isError ? (
          <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("empty.currencies")}</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{tCols("code")}</TableHead>
                <TableHead>{tCols("name")}</TableHead>
                <TableHead>{tCols("symbol")}</TableHead>
                <TableHead>{tCols("decimals")}</TableHead>
                <TableHead>{tCols("isBase")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((c) => (
                <TableRow key={c.code}>
                  <TableCell className="font-mono">{c.code}</TableCell>
                  <TableCell>{c.name}</TableCell>
                  <TableCell>{c.symbol ?? "—"}</TableCell>
                  <TableCell>{c.decimals}</TableCell>
                  <TableCell>
                    {c.is_base ? <Badge>Base</Badge> : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// FX Rates (history + create)
// ---------------------------------------------------------------------------
function RatesSection() {
  const t = useTranslations("fx");
  const tCols = useTranslations("fx.columns");
  const tFilters = useTranslations("fx.filters");

  const [from, setFrom] = React.useState<string>(ALL);
  const [to, setTo] = React.useState<string>(ALL);

  const { data: currencies } = useCurrencies();
  const codes = (currencies ?? []).map((c) => c.code);

  const filters = React.useMemo(
    () => ({
      from_currency: from === ALL ? undefined : from,
      to_currency: to === ALL ? undefined : to,
    }),
    [from, to],
  );

  const { data, isLoading, isError } = useFxRates(filters);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>{t("ratesTitle")}</CardTitle>
          <CardDescription>{t("ratesSubtitle")}</CardDescription>
        </div>
        <RbacGuard permissions={["fx:write"]}>
          <NewRateDialog availableCodes={codes} />
        </RbacGuard>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs uppercase">{tFilters("from")}</Label>
            <Select value={from} onValueChange={setFrom}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder={tFilters("anyCurrency")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("anyCurrency")}</SelectItem>
                {codes.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs uppercase">{tFilters("to")}</Label>
            <Select value={to} onValueChange={setTo}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder={tFilters("anyCurrency")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("anyCurrency")}</SelectItem>
                {codes.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {(from !== ALL || to !== ALL) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setFrom(ALL);
                setTo(ALL);
              }}
            >
              {tFilters("clear")}
            </Button>
          )}
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-md" />
            ))}
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
        ) : !data || data.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {t("empty.rates")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{tCols("from_currency")}</TableHead>
                <TableHead>{tCols("to_currency")}</TableHead>
                <TableHead>{tCols("rate")}</TableHead>
                <TableHead>{tCols("effective_from")}</TableHead>
                <TableHead>{tCols("effective_to")}</TableHead>
                <TableHead>{tCols("source")}</TableHead>
                <TableHead>{tCols("status")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((r) => (
                <TableRow
                  key={r.id}
                  className={r.effective_to === null ? "bg-primary/5" : undefined}
                >
                  <TableCell className="font-mono">{r.from_currency}</TableCell>
                  <TableCell className="font-mono">{r.to_currency}</TableCell>
                  <TableCell className="font-mono">
                    {Number(r.rate).toFixed(4)}
                  </TableCell>
                  <TableCell className="text-xs">
                    {new Date(r.effective_from).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs">
                    {r.effective_to
                      ? new Date(r.effective_to).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell>{r.source ?? "—"}</TableCell>
                  <TableCell>
                    {r.effective_to === null ? (
                      <Badge>{t("current")}</Badge>
                    ) : (
                      <Badge variant="outline">{t("expired")}</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// New Rate Dialog
// ---------------------------------------------------------------------------
function NewRateDialog({ availableCodes }: { availableCodes: string[] }) {
  const t = useTranslations("fx");
  const tFields = useTranslations("fx.fields");
  const tSources = useTranslations("fx.sources");
  const tCommon = useTranslations("common");
  const [open, setOpen] = React.useState(false);

  const schema = React.useMemo(
    () =>
      z
        .object({
          from_currency: z.string().length(3),
          to_currency: z.string().length(3),
          rate: z.preprocess(
            (v) => (typeof v === "string" ? Number(v) : v),
            z.number().positive(t("errors.rateInvalid")),
          ),
          effective_from: z.string().min(1),
          source: z.enum(FX_SOURCES),
        })
        .refine((v) => v.from_currency !== v.to_currency, {
          message: t("errors.samePair"),
          path: ["to_currency"],
        }),
    [t],
  );

  type Values = z.infer<typeof schema>;

  // Default `effective_from` = now en formato datetime-local (sin segundos).
  const nowLocal = React.useMemo(() => {
    const d = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }, []);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      from_currency: availableCodes[0] ?? "EUR",
      to_currency: availableCodes[1] ?? "AED",
      rate: 1,
      effective_from: nowLocal,
      source: "manual",
    },
    mode: "onBlur",
  });

  const create = useCreateFxRate();

  const onSubmit = async (values: Values) => {
    const payload: FXRateCreatePayload = {
      from_currency: values.from_currency,
      to_currency: values.to_currency,
      rate: values.rate,
      effective_from: new Date(values.effective_from).toISOString(),
      source: values.source,
    };
    try {
      await create.mutateAsync(payload);
      toast.success(t("feedback.created"));
      setOpen(false);
      form.reset({
        ...form.getValues(),
        rate: 1,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.saveFailed"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="h-4 w-4" /> {t("newRateButton")}
        </Button>
      </DialogTrigger>
      <DialogContent>
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
              label={tFields("from")}
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
              label={tFields("to")}
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
            label={tFields("rate")}
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
            label={tFields("effective_from")}
            error={form.formState.errors.effective_from?.message}
          >
            <Input type="datetime-local" {...form.register("effective_from")} />
          </Field>

          <Field
            label={tFields("source")}
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
                {FX_SOURCES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {tSources(s)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
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
