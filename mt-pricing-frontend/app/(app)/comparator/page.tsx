import Link from "next/link";
import { Construction } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * `/comparator` — placeholder Fase 1 del subsistema de comparación de productos.
 *
 * El comparator es un **research workstream** (ADR-012). Fase 1 deja sólo
 * hooks (tablas vacías + interfaces hexagonales + NoopComparatorService).
 * La UI real (validación humana asistida + dashboard de match status) se
 * implementa en Fase 1.5+ cuando el research entregue criterios go.
 *
 * Server component — no client state Fase 1.
 */
export default async function ComparatorPlaceholderPage() {
  const t = await getTranslations("comparator");

  return (
    <div className="flex h-full items-center justify-center p-8">
      <Card className="max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-3 grid size-12 place-items-center rounded-full bg-amber-100 text-amber-700">
            <Construction className="size-6" aria-hidden />
          </div>
          <CardTitle className="text-xl">{t("title")}</CardTitle>
          <CardDescription className="mt-2">
            {t("research_message")}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center">
          <Button asChild variant="outline">
            <Link href="/dashboard">{t("back_to_dashboard")}</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
