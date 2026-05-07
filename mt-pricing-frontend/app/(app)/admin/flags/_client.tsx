"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { FlagToggle } from "@/components/admin/flag-toggle";
import { KillSwitchDialog } from "@/components/admin/kill-switch-dialog";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
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
import { useAdminFlags } from "@/lib/hooks/admin/use-flags";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { type AdminFlag } from "@/lib/api/endpoints/admin-flags";

/**
 * Client del page `/admin/flags`. Muestra:
 *  1) Card "Kill switch" con big-red-button arriba (acción destructiva).
 *  2) Tabla de flags agrupados por `category`, con `<FlagToggle>`.
 */
export function AdminFlagsClient() {
  const t = useTranslations("admin.flags");
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("admin:flags:manage");

  const { data, isLoading, isError, refetch } = useAdminFlags();

  const grouped = React.useMemo<Record<string, AdminFlag[]>>(() => {
    const map: Record<string, AdminFlag[]> = {};
    (data ?? []).forEach((f) => {
      const cat = f.category ?? "misc";
      const bucket = map[cat] ?? [];
      bucket.push(f);
      map[cat] = bucket;
    });
    return map;
  }, [data]);

  return (
    <div className="space-y-6">
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">
            {t("killSwitch.cardTitle")}
          </CardTitle>
          <CardDescription>{t("killSwitch.cardDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          <KillSwitchDialog canWrite={canWrite} />
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <MtSkeleton key={i} height={42} className="w-full" />
          ))}
        </div>
      ) : isError ? (
        <MtError message={t("errors.loadFailed")} onRetry={() => void refetch()} />
      ) : !data || data.length === 0 ? (
        <MtEmpty title={t("empty.title")} hint={t("empty.hint")} />
      ) : (
        <div className="space-y-6">
          {Object.entries(grouped).map(([category, flags]) => (
            <Card key={category}>
              <CardHeader>
                <CardTitle className="text-base capitalize">
                  {category}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("columns.key")}</TableHead>
                      <TableHead>{t("columns.description")}</TableHead>
                      <TableHead>{t("columns.value")}</TableHead>
                      <TableHead className="w-32">
                        {t("columns.updatedAt")}
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {flags.map((flag) => (
                      <TableRow key={flag.key}>
                        <TableCell className="font-mono text-xs">
                          {flag.key}
                        </TableCell>
                        <TableCell className="max-w-md text-xs text-muted-foreground">
                          {flag.description ?? "—"}
                        </TableCell>
                        <TableCell>
                          <FlagToggle flag={flag} canWrite={canWrite} />
                        </TableCell>
                        <TableCell className="text-[10px] text-muted-foreground">
                          {new Date(flag.updated_at).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
