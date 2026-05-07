"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Eye } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { useImportRunsList } from "@/lib/hooks/imports-admin/use-imports-admin";
import type {
  ImportRunStatus,
  ImportType,
} from "@/lib/api/endpoints/imports-admin";
import { UploadSheet } from "./_components/upload-sheet";

const ALL = "__all__";

function StatusBadge({ status }: { status: ImportRunStatus }) {
  const variant: "default" | "secondary" | "destructive" | "outline" =
    status === "completed"
      ? "default"
      : status === "failed"
        ? "destructive"
        : status === "completed_with_errors"
          ? "secondary"
          : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}

export function ImportsAdminClient() {
  const t = useTranslations("admin.imports");
  const tCols = useTranslations("admin.imports.columns");
  const tFilters = useTranslations("admin.imports.filters");

  const [importType, setImportType] = React.useState<string>(ALL);
  const [statusFilter, setStatusFilter] = React.useState<string>(ALL);
  const [open, setOpen] = React.useState(false);

  const { data, isLoading, isError } = useImportRunsList({
    ...(importType !== ALL ? { import_type: importType as ImportType } : {}),
    ...(statusFilter !== ALL ? { status: statusFilter as ImportRunStatus } : {}),
    limit: 100,
  });

  return (
    <section className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {tFilters("importType")}
            </label>
            <Select value={importType} onValueChange={setImportType}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("any")}</SelectItem>
                <SelectItem value="pim">PIM</SelectItem>
                <SelectItem value="costs">costs</SelectItem>
                <SelectItem value="datasheets">datasheets</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {tFilters("status")}
            </label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("any")}</SelectItem>
                <SelectItem value="queued">queued</SelectItem>
                <SelectItem value="running">running</SelectItem>
                <SelectItem value="completed">completed</SelectItem>
                <SelectItem value="completed_with_errors">
                  completed_with_errors
                </SelectItem>
                <SelectItem value="failed">failed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <RbacGuard permissions={["imports:execute"]}>
          <Button onClick={() => setOpen(true)}>{t("uploadCta")}</Button>
        </RbacGuard>
      </div>

      <UploadSheet open={open} onOpenChange={setOpen} />

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
      ) : !data || data.items.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{tCols("type")}</TableHead>
              <TableHead>{tCols("filename")}</TableHead>
              <TableHead>{tCols("status")}</TableHead>
              <TableHead className="text-right">{tCols("total")}</TableHead>
              <TableHead className="text-right">{tCols("inserted")}</TableHead>
              <TableHead className="text-right">{tCols("updated")}</TableHead>
              <TableHead className="text-right">{tCols("errors")}</TableHead>
              <TableHead>{tCols("startedAt")}</TableHead>
              <TableHead>{tCols("finishedAt")}</TableHead>
              <TableHead className="text-right">{tCols("actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((r) => (
              <TableRow key={r.run_id}>
                <TableCell className="font-mono text-xs">
                  {r.import_type}
                </TableCell>
                <TableCell className="max-w-xs truncate">
                  {r.source_filename ?? "—"}
                </TableCell>
                <TableCell>
                  <StatusBadge status={r.status} />
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {r.total_rows ?? "—"}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {r.inserted_rows ?? "—"}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {r.updated_rows ?? "—"}
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {r.error_rows ?? 0}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {r.started_at
                    ? new Date(r.started_at).toLocaleString()
                    : "—"}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {r.finished_at
                    ? new Date(r.finished_at).toLocaleString()
                    : "—"}
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/admin/imports/${r.run_id}`}>
                      <Eye className="h-4 w-4" />
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
