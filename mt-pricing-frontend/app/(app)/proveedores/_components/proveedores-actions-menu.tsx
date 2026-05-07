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

/** Kebab menu por fila: ver, editar, archivar (soft-delete via PATCH active=false). */
export function ProveedoresActionsMenu({ supplier }: Props) {
  const router = useRouter();
  const t = useTranslations("proveedores.actions");
  const tCommon = useTranslations("common");
  const toggle = useToggleSupplierActive();
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  const handleToggle = async () => {
    try {
      await toggle.mutateAsync({ code: supplier.code, active: !supplier.active });
      toast.success(supplier.active ? t("deactivated") : t("activated"));
      setConfirmDelete(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tCommon("error"));
    }
  };

  const detailHref = `/proveedores/${encodeURIComponent(supplier.code)}`;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            aria-label={t("menu")}
            data-testid={`proveedor-actions-${supplier.code}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => router.push(detailHref)}>
            <Eye className="mr-2 h-4 w-4" /> {t("view")}
          </DropdownMenuItem>
          <RbacGuard permissions={["suppliers:write"]}>
            <DropdownMenuItem
              onClick={() => router.push(`${detailHref}/editar`)}
            >
              <Pencil className="mr-2 h-4 w-4" /> {t("edit")}
            </DropdownMenuItem>
            {supplier.active ? (
              <DropdownMenuItem onClick={() => setConfirmDelete(true)}>
                <PowerOff className="mr-2 h-4 w-4" /> {t("archive")}
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
        open={confirmDelete}
        onOpenChange={(open) => !open && setConfirmDelete(false)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("archive")}</DialogTitle>
            <DialogDescription>{t("deleteConfirm")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDelete(false)}>
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
