"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Eye, Pencil, Archive, ArchiveRestore, Trash2, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
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
import {
  useDeleteProduct,
  useToggleProductActive,
} from "@/lib/hooks/products/use-product-mutations";

interface Props {
  product: { id: string; sku: string; active: boolean };
  /** Si true, muestra etiqueta visible al lado del icono (variante en tabla). */
  compact?: boolean;
  /** Cuando se elimina, llama a onDeleted (para refresh listas, etc.). */
  onDeleted?: () => void;
}

export function SkuActionsMenu({ product, compact = false, onDeleted }: Props) {
  const t = useTranslations("catalog");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const deleteMut = useDeleteProduct();
  const toggleMut = useToggleProductActive();

  const handleDelete = async () => {
    try {
      await deleteMut.mutateAsync(product.id);
      toast.success(t("actions.deleted"));
      setConfirmOpen(false);
      onDeleted?.();
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.deleteFailed"));
    }
  };

  const handleToggleActive = async () => {
    try {
      const next = !product.active;
      await toggleMut.mutateAsync({ id: product.id, active: next });
      toast.success(next ? t("actions.unarchived") : t("actions.archived"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.saveFailed"));
    }
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size={compact ? "icon" : "sm"}
            aria-label={t("actions.menu")}
            data-testid={`sku-actions-${product.sku}`}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>{t("actions.menu")}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link href={`/catalogo/${product.sku}`} className="flex items-center gap-2">
              <Eye className="h-4 w-4" /> {t("actions.view")}
            </Link>
          </DropdownMenuItem>
          <RbacGuard permissions={["products:write"]}>
            <DropdownMenuItem asChild>
              <Link href={`/catalogo/${product.sku}/edit`} className="flex items-center gap-2">
                <Pencil className="h-4 w-4" /> {t("actions.edit")}
              </Link>
            </DropdownMenuItem>
          </RbacGuard>
          <RbacGuard permissions={["products:write"]}>
            <DropdownMenuItem onSelect={handleToggleActive} className="gap-2">
              {product.active ? (
                <>
                  <Archive className="h-4 w-4" /> {t("actions.archive")}
                </>
              ) : (
                <>
                  <ArchiveRestore className="h-4 w-4" /> {t("actions.unarchive")}
                </>
              )}
            </DropdownMenuItem>
          </RbacGuard>
          <DropdownMenuSeparator />
          <RbacGuard permissions={["products:delete"]}>
            <DropdownMenuItem
              onSelect={(e) => {
                e.preventDefault();
                setConfirmOpen(true);
              }}
              className="gap-2 text-destructive focus:text-destructive"
            >
              <Trash2 className="h-4 w-4" /> {t("actions.delete")}
            </DropdownMenuItem>
          </RbacGuard>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("actions.delete")}</DialogTitle>
            <DialogDescription>{t("actions.deleteConfirm")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              {tCommon("cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMut.isPending}
            >
              {t("actions.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
