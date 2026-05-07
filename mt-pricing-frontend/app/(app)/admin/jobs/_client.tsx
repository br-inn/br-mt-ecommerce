"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Eye, Power, PowerOff } from "lucide-react";
import { toast } from "sonner";

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
import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  jobsAdminApi,
  type JobDefinitionListItem,
  type JobStatus,
} from "@/lib/api/endpoints/jobs";
import {
  jobsKeys,
  useJobsList,
} from "@/lib/hooks/jobs/use-jobs";
import { useQueryClient } from "@tanstack/react-query";

function StatusBadge({ status }: { status: JobStatus | null }) {
  if (!status) return <Badge variant="outline">—</Badge>;
  const variant: "default" | "secondary" | "destructive" | "outline" =
    status === "success"
      ? "default"
      : status === "failure"
        ? "destructive"
        : status === "running"
          ? "secondary"
          : "outline";
  return <Badge variant={variant}>{status}</Badge>;
}

export function JobsListClient() {
  const t = useTranslations("admin.jobs");
  const tCols = useTranslations("admin.jobs.columns");
  const { data, isLoading, isError } = useJobsList({ limit: 200 });
  const qc = useQueryClient();

  const sorted = React.useMemo<JobDefinitionListItem[]>(() => {
    if (!data) return [];
    return [...data].sort((a, b) => {
      const ta = a.next_run_at ? Date.parse(a.next_run_at) : Infinity;
      const tb = b.next_run_at ? Date.parse(b.next_run_at) : Infinity;
      return ta - tb;
    });
  }, [data]);

  const toggleEnabled = async (job: JobDefinitionListItem) => {
    try {
      await jobsAdminApi.update(job.id, { enabled: !job.enabled });
      void qc.invalidateQueries({ queryKey: jobsKeys.all() });
      toast.success(
        job.enabled ? t("toast.disabled") : t("toast.enabled"),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.toggle"));
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded-md" />
        ))}
      </div>
    );
  }
  if (isError) {
    return <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>;
  }
  if (sorted.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-muted-foreground">
        {t("empty")}
      </p>
    );
  }

  return (
    <div className="rounded-md border bg-background">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{tCols("code")}</TableHead>
            <TableHead>{tCols("description")}</TableHead>
            <TableHead>{tCols("cron")}</TableHead>
            <TableHead>{tCols("queue")}</TableHead>
            <TableHead>{tCols("lastRun")}</TableHead>
            <TableHead>{tCols("lastStatus")}</TableHead>
            <TableHead>{tCols("nextRun")}</TableHead>
            <TableHead>{tCols("enabled")}</TableHead>
            <TableHead className="text-right">{tCols("actions")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((j) => (
            <TableRow key={j.id}>
              <TableCell className="font-mono text-xs">{j.code}</TableCell>
              <TableCell className="max-w-sm truncate">
                {j.description ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {j.schedule_type === "cron"
                  ? (j.cron_expression ?? "—")
                  : `${j.interval_seconds}s`}
              </TableCell>
              <TableCell>{j.queue}</TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {j.last_run_at
                  ? new Date(j.last_run_at).toLocaleString()
                  : "—"}
              </TableCell>
              <TableCell>
                <StatusBadge status={j.last_status} />
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                {j.next_run_at
                  ? new Date(j.next_run_at).toLocaleString()
                  : "—"}
              </TableCell>
              <TableCell>
                {j.enabled ? (
                  <Badge>{tCols("on")}</Badge>
                ) : (
                  <Badge variant="secondary">{tCols("off")}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                <div className="inline-flex gap-1">
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/admin/jobs/${j.id}`}>
                      <Eye className="h-4 w-4" />
                    </Link>
                  </Button>
                  <RbacGuard permissions={["jobs:write"]}>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => toggleEnabled(j)}
                      title={j.enabled ? tCols("disable") : tCols("enable")}
                    >
                      {j.enabled ? (
                        <PowerOff className="h-4 w-4" />
                      ) : (
                        <Power className="h-4 w-4" />
                      )}
                    </Button>
                  </RbacGuard>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
