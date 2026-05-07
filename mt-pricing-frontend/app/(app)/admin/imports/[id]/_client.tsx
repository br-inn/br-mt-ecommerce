"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { RbacGuard } from "@/components/auth/rbac-guard";
import {
  useImportRunDetail,
  useRunFromFixture,
} from "@/lib/hooks/imports-admin/use-imports-admin";
import type { ImportRunStatus } from "@/lib/api/endpoints/imports-admin";

interface Props {
  runId: string;
}

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

function fmtMs(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

export function ImportRunDetailClient({ runId }: Props) {
  const t = useTranslations("admin.imports.detail");
  const tCommon = useTranslations("common");
  const { data, isLoading, isError } = useImportRunDetail(runId);
  const fixture = useRunFromFixture();
  const [confirmRetry, setConfirmRetry] = React.useState(false);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return <p className="text-sm text-destructive">{t("loadFailed")}</p>;
  }

  const duration =
    data.started_at && data.finished_at
      ? Date.parse(data.finished_at) - Date.parse(data.started_at)
      : null;

  const handleRetry = async () => {
    try {
      await fixture.mutateAsync();
      toast.success(t("retryQueued"));
      setConfirmRetry(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("retryFailed"));
      setConfirmRetry(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Identity + status */}
      <Card>
        <CardHeader>
          <CardTitle className="font-mono text-base">{data.run_id}</CardTitle>
          <CardDescription>
            <StatusBadge status={data.status} />
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <Field label={t("type")}>{data.import_type}</Field>
          <Field label={t("filename")}>{data.source_filename ?? "—"}</Field>
          <Field label={t("duration")}>{fmtMs(duration)}</Field>
          <Field label={t("startedAt")}>
            {data.started_at ? new Date(data.started_at).toLocaleString() : "—"}
          </Field>
          <Field label={t("finishedAt")}>
            {data.finished_at
              ? new Date(data.finished_at).toLocaleString()
              : "—"}
          </Field>
          <Field label={t("celeryTaskId")}>
            <span className="font-mono text-xs">
              {data.celery_task_id ?? "—"}
            </span>
          </Field>
        </CardContent>
      </Card>

      {/* Counters */}
      <Card>
        <CardHeader>
          <CardTitle>{t("countersTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 md:grid-cols-5">
          <Counter label={t("totalRows")} value={data.total_rows} />
          <Counter label={t("inserted")} value={data.inserted_rows} tone="ok" />
          <Counter label={t("updated")} value={data.updated_rows} tone="ok" />
          <Counter label={t("skipped")} value={data.skipped_rows} />
          <Counter label={t("errors")} value={data.error_rows} tone="bad" />
        </CardContent>
      </Card>

      {/* Errors */}
      {data.errors_total > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>
              {t("errorsTitle")}{" "}
              <Badge variant="destructive">{data.errors_total}</Badge>
            </CardTitle>
            <CardDescription>{t("errorsSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("errorRow")}</TableHead>
                    <TableHead>{t("errorSku")}</TableHead>
                    <TableHead>{t("errorField")}</TableHead>
                    <TableHead>{t("errorMessage")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.errors.map((e, idx) => (
                    <TableRow key={`${e.row}-${idx}`}>
                      <TableCell className="font-mono text-xs">
                        {e.row}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {e.sku ?? "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {e.field ?? "—"}
                      </TableCell>
                      <TableCell className="text-xs text-destructive">
                        {e.error}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {data.errors.length < data.errors_total ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {t("errorsCapped", {
                  shown: data.errors.length,
                  total: data.errors_total,
                })}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {/* Summary */}
      <Card>
        <CardHeader>
          <CardTitle>{t("summaryTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="max-h-96 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">
            {JSON.stringify(data.summary ?? {}, null, 2)}
          </pre>
        </CardContent>
      </Card>

      {/* Retry */}
      {data.status === "failed" ? (
        <RbacGuard permissions={["imports:execute"]}>
          <Card>
            <CardHeader>
              <CardTitle>{t("retryTitle")}</CardTitle>
              <CardDescription>{t("retrySubtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setConfirmRetry(true)}
                disabled={fixture.isPending}
              >
                <RotateCw className="h-4 w-4" />
                {t("retryAction")}
              </Button>
            </CardContent>
          </Card>
        </RbacGuard>
      ) : null}

      <ConfirmDialog
        open={confirmRetry}
        onOpenChange={setConfirmRetry}
        title={t("confirmRetryTitle")}
        description={t("confirmRetryDesc")}
        confirmLabel={tCommon("confirm")}
        busy={fixture.isPending}
        onConfirm={handleRetry}
      />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs uppercase text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}

function Counter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | null;
  tone?: "ok" | "bad";
}) {
  const color =
    tone === "ok"
      ? "text-emerald-600"
      : tone === "bad"
        ? "text-destructive"
        : "text-foreground";
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-semibold ${color}`}>
        {value ?? 0}
      </p>
    </div>
  );
}
