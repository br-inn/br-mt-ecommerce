"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TranslationStatusPill } from "@/components/domain/translation-status-pill";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { useProduct } from "@/lib/hooks/products/use-product";
import {
  useApproveTranslation,
  useProductTranslations,
  useUpsertTranslation,
} from "@/lib/hooks/products/use-translations";
import type { Language, ProductTranslationRead } from "@/lib/api/endpoints/products";
import {
  getProductDescription,
  getProductName,
} from "@/lib/utils/product-display";

const translationSchema = z.object({
  name: z.string().min(2),
  description: z.string().optional(),
  marketing_copy: z.string().optional(),
  applications_text: z.string().optional(),
  technical_limits: z.string().optional(),
  marketing_features: z.string().optional(),
  meta_title: z.string().optional(),
  meta_description: z.string().optional(),
  notes: z.string().optional(),
});
type TranslationFormValues = z.infer<typeof translationSchema>;

export function TranslationsTab({ sku }: { sku: string }) {
  const t = useTranslations("catalog.translations");
  const { data: product, isLoading: loadingProduct } = useProduct(sku);
  const { data: translations, isLoading: loadingTranslations } = useProductTranslations(
    product?.id,
  );

  if (loadingProduct || loadingTranslations) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!product) return null;

  const findTranslation = (lang: Language): ProductTranslationRead | undefined =>
    translations?.find((tr) => tr.language === lang);

  const enTranslation = translations?.find((tr) => tr.language === ("en" as Language));

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {/* Canónico EN — solo lectura */}
      <Card>
        <CardHeader>
          <CardTitle>{t("canonical")}</CardTitle>
          <CardDescription>
            <TranslationStatusPill language="en" status="approved" />
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <CanonicalField label={t("fields.name")} value={getProductName(product)} />
          <CanonicalField label={t("fields.description")} value={getProductDescription(product)} pre />
          {enTranslation?.marketing_copy ? (
            <CanonicalField label={t("fields.marketing_copy")} value={enTranslation.marketing_copy} pre />
          ) : null}
          {enTranslation?.applications_text ? (
            <CanonicalField label={t("fields.applications_text")} value={enTranslation.applications_text} pre />
          ) : null}
          {enTranslation?.technical_limits ? (
            <CanonicalField label={t("fields.technical_limits")} value={enTranslation.technical_limits} pre />
          ) : null}
          {enTranslation?.meta_title ? (
            <CanonicalField label={t("fields.meta_title")} value={enTranslation.meta_title} />
          ) : null}
        </CardContent>
      </Card>

      <TranslationForm productId={product.id} lang="es" translation={findTranslation("es")} />
      <TranslationForm productId={product.id} lang="ar" translation={findTranslation("ar")} />
    </div>
  );
}

function CanonicalField({ label, value, pre = false }: { label: string; value: string | null | undefined; pre?: boolean }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      {pre
        ? <p className="mt-0.5 whitespace-pre-wrap text-sm">{value ?? "—"}</p>
        : <p className="mt-0.5 text-sm font-medium">{value ?? "—"}</p>
      }
    </div>
  );
}

function TranslationForm({
  productId,
  lang,
  translation,
}: {
  productId: string;
  lang: Language;
  translation: ProductTranslationRead | undefined;
}) {
  const t = useTranslations("catalog.translations");
  const tCommon = useTranslations("common");
  const upsert = useUpsertTranslation(productId);
  const approve = useApproveTranslation(productId);
  const [showMarketing, setShowMarketing] = React.useState(false);
  const [showSeo, setShowSeo] = React.useState(false);

  const form = useForm<TranslationFormValues>({
    resolver: zodResolver(translationSchema),
    defaultValues: {
      name: translation?.name ?? "",
      description: translation?.description ?? "",
      marketing_copy: translation?.marketing_copy ?? "",
      applications_text: translation?.applications_text ?? "",
      technical_limits: translation?.technical_limits ?? "",
      marketing_features: translation?.marketing_features ?? "",
      meta_title: translation?.meta_title ?? "",
      meta_description: translation?.meta_description ?? "",
      notes: translation?.notes ?? "",
    },
  });

  React.useEffect(() => {
    form.reset({
      name: translation?.name ?? "",
      description: translation?.description ?? "",
      marketing_copy: translation?.marketing_copy ?? "",
      applications_text: translation?.applications_text ?? "",
      technical_limits: translation?.technical_limits ?? "",
      marketing_features: translation?.marketing_features ?? "",
      meta_title: translation?.meta_title ?? "",
      meta_description: translation?.meta_description ?? "",
      notes: translation?.notes ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [translation?.language, translation?.name, translation?.description, translation?.status]);

  const dir = lang === "ar" ? "rtl" : "ltr";
  const langLabel = t(`languages.${lang}`);

  const toUpsertPayload = (values: TranslationFormValues) => ({
    name: values.name,
    description: values.description ?? null,
    marketing_copy: values.marketing_copy ?? null,
    applications_text: values.applications_text ?? null,
    technical_limits: values.technical_limits ?? null,
    marketing_features: values.marketing_features ?? null,
    meta_title: values.meta_title ?? null,
    meta_description: values.meta_description ?? null,
    notes: values.notes ?? null,
  });

  const onSaveDraft = async (values: TranslationFormValues) => {
    try {
      await upsert.mutateAsync({ lang, payload: toUpsertPayload(values) });
      toast.success(t("feedback.saved"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("feedback.saveFailed"));
    }
  };

  const onRequestApproval = async () => {
    // Backend infiere "pending" cuando la traducción está draft + se "guarda"
    // sin nuevos cambios; aquí simplemente persistimos lo que haya y mostramos
    // toast. Si el backend expone endpoint dedicado lo migramos.
    await form.handleSubmit(async (values) => {
      try {
        await upsert.mutateAsync({ lang, payload: toUpsertPayload(values) });
        toast.success(t("feedback.requested"));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : t("feedback.saveFailed"));
      }
    })();
  };

  const onApprove = async () => {
    try {
      await approve.mutateAsync(lang);
      toast.success(t("feedback.approved"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("feedback.saveFailed"));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{langLabel}</CardTitle>
        <CardDescription className="flex items-center gap-2">
          <TranslationStatusPill language={lang} status={translation?.status ?? null} />
          {lang === "ar" ? <span className="text-xs">{t("rtlNote")}</span> : null}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-3"
          onSubmit={form.handleSubmit(onSaveDraft)}
          dir={dir}
          noValidate
        >
          {/* Contenido principal */}
          <div className="space-y-1.5">
            <Label htmlFor={`name-${lang}`}>{t("fields.name")}</Label>
            <Input id={`name-${lang}`} {...form.register("name")} dir={dir} />
            {form.formState.errors.name ? (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={`desc-${lang}`}>{t("fields.description")}</Label>
            <textarea
              id={`desc-${lang}`}
              dir={dir}
              rows={3}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              {...form.register("description")}
            />
          </div>

          {/* Marketing — expandible */}
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded border border-dashed px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowMarketing((v) => !v)}
          >
            <span className="flex-1 text-left">{t("sections.marketing")}</span>
            <span>{showMarketing ? "▲" : "▼"}</span>
          </button>
          {showMarketing ? (
            <div className="space-y-3 rounded-md border bg-muted/20 p-3">
              <div className="space-y-1.5">
                <Label htmlFor={`mkt-${lang}`}>{t("fields.marketing_copy")}</Label>
                <textarea id={`mkt-${lang}`} dir={dir} rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("marketing_copy")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`app-${lang}`}>{t("fields.applications_text")}</Label>
                <textarea id={`app-${lang}`} dir={dir} rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("applications_text")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`tl-${lang}`}>{t("fields.technical_limits")}</Label>
                <textarea id={`tl-${lang}`} dir={dir} rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("technical_limits")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`mf-${lang}`}>{t("fields.marketing_features")}</Label>
                <textarea id={`mf-${lang}`} dir={dir} rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("marketing_features")} />
              </div>
            </div>
          ) : null}

          {/* SEO — expandible */}
          <button
            type="button"
            className="flex w-full items-center gap-2 rounded border border-dashed px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            onClick={() => setShowSeo((v) => !v)}
          >
            <span className="flex-1 text-left">{t("sections.seo")}</span>
            <span>{showSeo ? "▲" : "▼"}</span>
          </button>
          {showSeo ? (
            <div className="space-y-3 rounded-md border bg-muted/20 p-3">
              <div className="space-y-1.5">
                <Label htmlFor={`mt-${lang}`}>{t("fields.meta_title")}</Label>
                <Input id={`mt-${lang}`} dir={dir} {...form.register("meta_title")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`md-${lang}`}>{t("fields.meta_description")}</Label>
                <textarea id={`md-${lang}`} dir={dir} rows={2}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("meta_description")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={`nt-${lang}`}>{t("fields.notes")}</Label>
                <textarea id={`nt-${lang}`} dir={dir} rows={2}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  {...form.register("notes")} />
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-1" dir="ltr">
            <RbacGuard permissions={["products:write"]}>
              <Button type="submit" size="sm" variant="outline" disabled={upsert.isPending}>
                {upsert.isPending ? tCommon("loading") : t("actions.saveDraft")}
              </Button>
            </RbacGuard>
            <RbacGuard permissions={["products:write"]}>
              <Button type="button" size="sm" variant="secondary" onClick={onRequestApproval}>
                {t("actions.requestApproval")}
              </Button>
            </RbacGuard>
            <RbacGuard permissions={["translations:approve"]}>
              <Button
                type="button"
                size="sm"
                onClick={onApprove}
                disabled={approve.isPending || translation?.status === "approved"}
              >
                {t("actions.approve")}
              </Button>
            </RbacGuard>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
