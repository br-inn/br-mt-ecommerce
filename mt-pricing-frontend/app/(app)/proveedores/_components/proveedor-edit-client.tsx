"use client";

import { useTranslations } from "next-intl";

import { Skeleton } from "@/components/ui/skeleton";
import { useSupplier } from "@/lib/hooks/suppliers/use-suppliers";
import { ProveedorFormClient } from "./proveedor-form-client";

interface Props {
  code: string;
}

/** Carga el proveedor y monta el form en modo edit. */
export function ProveedorEditClient({ code }: Props) {
  const t = useTranslations("proveedores");
  const { data: supplier, isLoading, isError } = useSupplier(code);

  if (isLoading) {
    return <Skeleton className="h-72 w-full rounded-lg" />;
  }
  if (isError || !supplier) {
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4 text-sm text-destructive">
        {t("errors.notFound")}
      </div>
    );
  }
  return <ProveedorFormClient initial={supplier} />;
}
