"use client";

import { useTranslations } from "next-intl";
import { InboxIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePermissions } from "@/lib/hooks/use-permissions";

/**
 * Cola de validación — placeholder.
 *
 * Muestra la estructura de la tabla de candidatos en zona gris (score 30-74,
 * method="human_queue") pero sin datos reales: el endpoint backend no está
 * implementado aún. Cuando esté disponible, basta con conectar el hook de
 * react-query y reemplazar el estado vacío.
 */
export function ColaValidacionClient() {
  const t = useTranslations("admin.scraper");
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("products:write");

  // TODO: replace with real hook when backend endpoint is ready.
  const candidates: never[] = [];
  const isLoading = false;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("cola.title")}</CardTitle>
        <CardDescription>{t("cola.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-10 w-full animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        ) : candidates.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <InboxIcon className="h-10 w-10 text-muted-foreground/40" />
            <div className="space-y-1">
              <p className="text-sm font-medium">{t("cola.emptyTitle")}</p>
              <p className="max-w-sm text-xs text-muted-foreground">
                {t("cola.emptyHint")}
              </p>
            </div>
          </div>
        ) : (
          /* Data table — ready to be wired when real data arrives */
          <div className="rounded-md border bg-background">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("cola.columns.sku")}</TableHead>
                  <TableHead>{t("cola.columns.asin")}</TableHead>
                  <TableHead className="w-20 text-right">{t("cola.columns.score")}</TableHead>
                  <TableHead>{t("cola.columns.method")}</TableHead>
                  <TableHead className="text-right">{t("cola.columns.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* rows would be mapped here */}
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="py-10 text-center text-sm text-muted-foreground"
                  >
                    {t("cola.emptyTitle")}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
        )}

        {/* Action buttons — disabled until real data is available */}
        {candidates.length > 0 && canWrite ? (
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" size="sm" disabled>
              {t("cola.actions.reject")}
            </Button>
            <Button size="sm" disabled>
              {t("cola.actions.validate")}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
