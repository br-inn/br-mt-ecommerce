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

const translationSchema = z.object({
  name: z.string().min(2),
  description: z.string().optional(),
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

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>{t("canonical")}</CardTitle>
          <CardDescription>
            <TranslationStatusPill language="en" status="approved" />
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label className="text-xs text-muted-foreground">name</Label>
            <p className="text-sm font-medium">{product.name_en}</p>
          </div>
          <div>
            <Label className="text-xs text-muted-foreground">description</Label>
            <p className="whitespace-pre-wrap text-sm">{product.description_en ?? "—"}</p>
          </div>
        </CardContent>
      </Card>

      <TranslationForm productId={product.id} lang="es" translation={findTranslation("es")} />
      <TranslationForm productId={product.id} lang="ar" translation={findTranslation("ar")} />
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

  const form = useForm<TranslationFormValues>({
    resolver: zodResolver(translationSchema),
    defaultValues: {
      name: translation?.name ?? "",
      description: translation?.description ?? "",
    },
  });

  React.useEffect(() => {
    form.reset({
      name: translation?.name ?? "",
      description: translation?.description ?? "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [translation?.language, translation?.name, translation?.description, translation?.status]);

  const dir = lang === "ar" ? "rtl" : "ltr";
  const langLabel = t(`languages.${lang}`);

  // Convierte el form (description?: string | undefined) al payload de API
  // (description: string | null) para satisfacer exactOptionalPropertyTypes.
  const toUpsertPayload = (values: TranslationFormValues) => ({
    name: values.name,
    description: values.description ?? null,
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
              rows={4}
              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              {...form.register("description")}
            />
          </div>
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
