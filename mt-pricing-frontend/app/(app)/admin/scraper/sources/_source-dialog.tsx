"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

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
  useCreateScraperSource,
  useUpdateScraperSource,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  ScraperSourcesApiError,
  type ScraperSourceRead,
} from "@/lib/api/endpoints/scraper-sources";

const schema = z.object({
  name: z.string().min(1).max(160),
  slug: z
    .string()
    .min(1)
    .max(80)
    .regex(/^[a-z0-9-]+$/, "Lowercase letters, numbers and hyphens only."),
  base_url: z.string().url(),
  destination_profile: z.enum(["competitor_price", "product_data"]),
  fetch_mode: z.enum(["static", "headless", "stealth"]),
  description: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  mode: "create" | "edit";
  source?: ScraperSourceRead;
  open: boolean;
  onClose: () => void;
  onSuccess?: (source: ScraperSourceRead) => void;
}

export function SourceDialog({ mode, source, open, onClose, onSuccess }: Props) {
  const t = useTranslations("admin.scraperSources.info");
  const create = useCreateScraperSource();
  const update = useUpdateScraperSource();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: source?.name ?? "",
      slug: source?.slug ?? "",
      base_url: source?.base_url ?? "",
      destination_profile: source?.destination_profile ?? "competitor_price",
      fetch_mode: source?.fetch_mode ?? "static",
      description: source?.description ?? "",
    },
  });

  React.useEffect(() => {
    if (open) {
      form.reset({
        name: source?.name ?? "",
        slug: source?.slug ?? "",
        base_url: source?.base_url ?? "",
        destination_profile: source?.destination_profile ?? "competitor_price",
        fetch_mode: source?.fetch_mode ?? "static",
        description: source?.description ?? "",
      });
    }
  }, [open, source, form]);

  const onSubmit = async (values: FormValues) => {
    const payload = { ...values, description: values.description ?? null };
    try {
      let result: ScraperSourceRead;
      if (mode === "create") {
        result = await create.mutateAsync(payload);
        toast.success(t("createSuccess"));
      } else {
        result = await update.mutateAsync({ id: source!.id, data: payload });
        toast.success(t("updateSuccess"));
      }
      onSuccess?.(result);
      onClose();
    } catch (err) {
      if (err instanceof ScraperSourcesApiError && err.status === 409) {
        form.setError("slug", { message: t("errorDuplicateSlug") });
      } else {
        toast.error(t("errorGeneric"));
      }
    }
  };

  const isPending = create.isPending || update.isPending;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{mode === "create" ? t("createTitle") : t("editTitle")}</DialogTitle>
        </DialogHeader>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="ss-name">{t("name")}</Label>
            <Input id="ss-name" {...form.register("name")} />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-slug">{t("slug")}</Label>
            <Input
              id="ss-slug"
              {...form.register("slug")}
              disabled={mode === "edit"}
              className={mode === "edit" ? "text-muted-foreground" : ""}
            />
            <p className="text-xs text-muted-foreground">{t("slugHint")}</p>
            {form.formState.errors.slug && (
              <p className="text-xs text-destructive">{form.formState.errors.slug.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-url">{t("baseUrl")}</Label>
            <Input id="ss-url" {...form.register("base_url")} placeholder="https://" />
            {form.formState.errors.base_url && (
              <p className="text-xs text-destructive">{form.formState.errors.base_url.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-dest">{t("destinationProfile")}</Label>
            <Select
              value={form.watch("destination_profile")}
              onValueChange={(v) =>
                form.setValue("destination_profile", v as "competitor_price" | "product_data")
              }
            >
              <SelectTrigger id="ss-dest">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="competitor_price">competitor_price</SelectItem>
                <SelectItem value="product_data">product_data</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-mode">{t("fetchMode")}</Label>
            <Select
              value={form.watch("fetch_mode")}
              onValueChange={(v) => form.setValue("fetch_mode", v as "static")}
            >
              <SelectTrigger id="ss-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="static">static</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ss-desc">{t("descriptionLabel")}</Label>
            <Input id="ss-desc" {...form.register("description")} />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
              {t("cancel")}
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? t("saving") : t("save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
