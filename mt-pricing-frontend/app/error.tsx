"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errors");
  const tCommon = useTranslations("common");

  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("Error boundary:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-semibold">{t("boundaryTitle")}</h1>
      <p className="max-w-md text-muted-foreground">{t("boundaryDescription")}</p>
      <Button onClick={reset}>{tCommon("retry")}</Button>
    </div>
  );
}
