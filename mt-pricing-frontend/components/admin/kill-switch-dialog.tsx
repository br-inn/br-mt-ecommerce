"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useKillSwitch } from "@/lib/hooks/admin/use-flags";

interface Props {
  /** RBAC: si false el botón se renderiza deshabilitado. */
  canWrite: boolean;
}

/**
 * Big-red-button kill-switch dialog (US-1A-09-08 + US-1A-DEV-01 frontend).
 *
 * - Acción destructiva: requiere `reason` (>= 10 chars) antes de POST.
 * - Confirmación doble: dialog + estado pending del botón final.
 * - Tras éxito, el list de flags se invalida automáticamente.
 */
export function KillSwitchDialog({ canWrite }: Props) {
  const t = useTranslations("admin.flags.killSwitch");
  const tCommon = useTranslations("common");
  const [open, setOpen] = React.useState(false);
  const mutation = useKillSwitch();

  const schema = React.useMemo(
    () =>
      z.object({
        reason: z
          .string()
          .min(10, t("errors.reasonRequired"))
          .max(512),
      }),
    [t],
  );
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { reason: "" },
    mode: "onBlur",
  });

  const onSubmit = async (values: Values) => {
    try {
      const resp = await mutation.mutateAsync({ reason: values.reason });
      toast.success(
        t("toast.success", { count: resp.flags_disabled.length }),
      );
      setOpen(false);
      form.reset({ reason: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.failed"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="destructive"
          disabled={!canWrite}
          className="gap-2"
          data-testid="kill-switch-trigger"
        >
          <AlertTriangle className="h-4 w-4" />
          {t("trigger")}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            {t("title")}
          </DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
          className="space-y-3"
        >
          <div className="space-y-1.5">
            <Label htmlFor="kill-switch-reason">{t("reasonLabel")}</Label>
            <textarea
              id="kill-switch-reason"
              {...form.register("reason")}
              rows={3}
              maxLength={512}
              placeholder={t("reasonPlaceholder")}
              className="flex min-h-[72px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="kill-switch-reason"
            />
            {form.formState.errors.reason ? (
              <p className="text-xs text-destructive">
                {form.formState.errors.reason.message}
              </p>
            ) : null}
          </div>
          <div
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive"
          >
            <strong className="block font-semibold">{t("warningTitle")}</strong>
            <span>{t("warningBody")}</span>
          </div>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={mutation.isPending}
            >
              {tCommon("cancel")}
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={mutation.isPending}
              data-testid="kill-switch-confirm"
            >
              {mutation.isPending ? tCommon("loading") : t("confirm")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
