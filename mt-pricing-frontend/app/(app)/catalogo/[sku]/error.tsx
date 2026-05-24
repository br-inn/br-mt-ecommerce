"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export default function ProductDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errors");
  const tCommon = useTranslations("common");

  useEffect(() => {
    console.error("[catalog/[sku]] error", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <h2 className="text-xl font-semibold">{t("boundaryTitle")}</h2>
      <p className="max-w-sm text-sm text-muted-foreground">{t("boundaryDescription")}</p>
      <Button onClick={reset}>{tCommon("retry")}</Button>
    </div>
  );
}
