"use client";

import * as React from "react";
import { Power, PowerOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  type CurrencyAdmin,
  CurrenciesApiError,
} from "@/lib/api/endpoints/currencies";
import {
  useCurrenciesAdmin,
  useSetCurrencyActive,
} from "@/lib/hooks/currencies/use-currencies";

/**
 * `CurrencyTable` — admin DataTable de currencies con activate/deactivate
 * (US-1A-05-01-S3).
 *
 * - Render todas las filas (incluye inactivas) — el seed son 4: AED, EUR,
 *   USD, SAR.
 * - Botón activate/deactivate: dialog confirma la acción + reason opcional.
 * - Bloquea desactivar la moneda base (`is_base=true`) en UI ANTES del POST.
 * - Captura `error.code === 'cannot_deactivate_base_currency'` y muestra
 *   toast con mensaje localizado.
 */
export function CurrencyTable() {
  const t = useTranslations("currencies");
  const { data, isLoading, isError } = useCurrenciesAdmin();
  const [target, setTarget] = React.useState<CurrencyAdmin | null>(null);
  const [reason, setReason] = React.useState("");
  const setActive = useSetCurrencyActive();

  const handleConfirm = async () => {
    if (!target) return;
    try {
      await setActive.mutateAsync({
        code: target.code,
        payload: {
          active: !target.active,
          reason: reason.trim() ? reason.trim() : null,
        },
      });
      toast.success(
        target.active
          ? t("toasts.deactivated", { code: target.code })
          : t("toasts.activated", { code: target.code }),
      );
      setTarget(null);
      setReason("");
    } catch (err) {
      let message = t("errors.saveFailed");
      if (err instanceof CurrenciesApiError) {
        const detail = err.detail as
          | { detail?: { code?: string; title?: string } }
          | undefined;
        const code = detail?.detail?.code;
        if (code === "cannot_deactivate_base_currency") {
          message = t("errors.cannotDeactivateBase");
        } else if (detail?.detail?.title) {
          message = detail.detail.title;
        }
      }
      toast.error(message);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>;
  }

  const rows = data ?? [];

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("columns.code")}</TableHead>
            <TableHead>{t("columns.name")}</TableHead>
            <TableHead>{t("columns.symbol")}</TableHead>
            <TableHead className="w-24">{t("columns.isBase")}</TableHead>
            <TableHead className="w-24">{t("columns.active")}</TableHead>
            <TableHead className="w-40 text-right">
              {t("columns.actions")}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((c) => (
            <TableRow
              key={c.code}
              className={!c.active ? "opacity-60" : undefined}
            >
              <TableCell className="font-mono">{c.code}</TableCell>
              <TableCell>{c.name}</TableCell>
              <TableCell>{c.symbol ?? "—"}</TableCell>
              <TableCell>
                {c.is_base ? <Badge>{t("base")}</Badge> : "—"}
              </TableCell>
              <TableCell>
                {c.active ? (
                  <Badge variant="default">{t("statuses.active")}</Badge>
                ) : (
                  <Badge variant="outline">{t("statuses.inactive")}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <RbacGuard permissions={["currencies:manage"]}>
                  <Button
                    type="button"
                    size="sm"
                    variant={c.active ? "outline" : "default"}
                    disabled={c.is_base && c.active}
                    onClick={() => {
                      setTarget(c);
                      setReason("");
                    }}
                  >
                    {c.active ? (
                      <>
                        <PowerOff className="h-4 w-4" />{" "}
                        {t("actions.deactivate")}
                      </>
                    ) : (
                      <>
                        <Power className="h-4 w-4" /> {t("actions.activate")}
                      </>
                    )}
                  </Button>
                </RbacGuard>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog
        open={target !== null}
        onOpenChange={(o) => !o && setTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {target?.active
                ? t("dialog.deactivateTitle", { code: target?.code ?? "" })
                : t("dialog.activateTitle", { code: target?.code ?? "" })}
            </DialogTitle>
            <DialogDescription>
              {target?.active
                ? t("dialog.deactivateDescription")
                : t("dialog.activateDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="currency-reason">{t("dialog.reasonLabel")}</Label>
            <Input
              id="currency-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("dialog.reasonPlaceholder")}
              maxLength={512}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setTarget(null)}
              disabled={setActive.isPending}
            >
              {t("dialog.cancel")}
            </Button>
            <Button
              type="button"
              variant={target?.active ? "destructive" : "default"}
              onClick={handleConfirm}
              disabled={setActive.isPending}
            >
              {setActive.isPending ? t("dialog.saving") : t("dialog.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
