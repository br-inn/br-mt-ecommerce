"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { MoreHorizontal, Pencil, Power, PowerOff, Eye } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { useToggleSupplierActive } from "@/lib/hooks/suppliers/use-suppliers";
import type { Supplier } from "@/lib/api/endpoints/suppliers";

interface Props {
  supplier: Supplier;
}

/** Kebab menu por fila: ver, editar, activar/desactivar (soft). */
export function SupplierActionsMenu({ supplier }: Props) {
  const router = useRouter();
  const t = useTranslations("suppliers.actions");
  const tCommon = useTranslations("common");
  const toggle = useToggleSupplierActive();
  const [confirmDeactivate, setConfirmDeactivate] = React.useState(false);

  const handleToggle = async () => {
    try {
      await toggle.mutateAsync({ code: supplier.code, active: !supplier.active });
      toast.success(supplier.active ? t("deactivated") : t("activated"));
      setConfirmDeactivate(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const detailHref = `/suppliers/${encodeURIComponent(supplier.code)}`;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("menu")}
            data-testid={`supplier-actions-${supplier.code}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => router.push(detailHref)}>
            <Eye className="mr-2 h-4 w-4" /> {t("view")}
          </DropdownMenuItem>
          <RbacGuard permissions={["suppliers:write"]}>
            <DropdownMenuItem onClick={() => router.push(`${detailHref}?edit=1`)}>
              <Pencil className="mr-2 h-4 w-4" /> {t("edit")}
            </DropdownMenuItem>
            {supplier.active ? (
              <DropdownMenuItem onClick={() => setConfirmDeactivate(true)}>
                <PowerOff className="mr-2 h-4 w-4" /> {t("deactivate")}
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onClick={handleToggle}>
                <Power className="mr-2 h-4 w-4" /> {t("activate")}
              </DropdownMenuItem>
            )}
          </RbacGuard>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog
        open={confirmDeactivate}
        onOpenChange={(open) => !open && setConfirmDeactivate(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deactivate")}</DialogTitle>
            <DialogDescription>{t("deactivateConfirm")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeactivate(false)}>
              {tCommon("cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleToggle}
              disabled={toggle.isPending}
            >
              {tCommon("confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
