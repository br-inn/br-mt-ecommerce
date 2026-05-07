"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Play } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { AuditTimeline } from "@/components/domain/audit-timeline";
import {
  cronPreviewNext,
  useJobDetail,
  useJobRuns,
  useRunJobNow,
  useUpdateJob,
} from "@/lib/hooks/jobs/use-jobs";
import type { JobStatus } from "@/lib/api/endpoints/jobs";

interface Props {
  jobId: string;
}

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

export function JobDetailClient({ jobId }: Props) {
  const t = useTranslations("admin.jobs");
  const { data: job, isLoading, isError } = useJobDetail(jobId);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !job) {
    return <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>;
  }

  return <JobDetailLoaded jobId={jobId} job={job} />;
}

interface LoadedProps {
  jobId: string;
  job: NonNullable<ReturnType<typeof useJobDetail>["data"]>;
}

function JobDetailLoaded({ jobId, job }: LoadedProps) {
  const tDetail = useTranslations("admin.jobs.detail");
  const tCommon = useTranslations("common");

  const { data: runsPage } = useJobRuns(jobId);
  const update = useUpdateJob(jobId);
  const runNow = useRunJobNow(jobId);

  const [confirmRun, setConfirmRun] = React.useState(false);

  const schema = React.useMemo(
    () =>
      z.object({
        cron_expression: z.string(),
        queue: z.string().min(1),
        argsJson: z.string().refine(
          (v) => {
            try {
              const parsed = JSON.parse(v);
              return Array.isArray(parsed);
            } catch {
              return false;
            }
          },
          { message: tDetail("errors.argsJson") },
        ),
        kwargsJson: z.string().refine(
          (v) => {
            try {
              const parsed = JSON.parse(v);
              return (
                typeof parsed === "object" &&
                parsed !== null &&
                !Array.isArray(parsed)
              );
            } catch {
              return false;
            }
          },
          { message: tDetail("errors.kwargsJson") },
        ),
        enabled: z.boolean(),
      }),
    [tDetail],
  );
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      cron_expression: job.cron_expression ?? "",
      queue: job.queue,
      argsJson: JSON.stringify(job.args ?? [], null, 2),
      kwargsJson: JSON.stringify(job.kwargs ?? {}, null, 2),
      enabled: job.enabled,
    },
  });

  const cronWatch = form.watch("cron_expression");
  const cronPreview = React.useMemo(
    () => cronPreviewNext(cronWatch ?? "", 5),
    [cronWatch],
  );

  const onSubmit = async (values: Values) => {
    try {
      await update.mutateAsync({
        cron_expression: values.cron_expression || null,
        queue: values.queue,
        args: JSON.parse(values.argsJson) as unknown[],
        kwargs: JSON.parse(values.kwargsJson) as Record<string, unknown>,
        enabled: values.enabled,
      });
      toast.success(tDetail("savedToast"));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("errors.save"));
    }
  };

  const handleRunNow = async () => {
    try {
      await runNow.mutateAsync();
      toast.success(tDetail("runNowQueued"));
      setConfirmRun(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : tDetail("errors.runNow"));
      setConfirmRun(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Identity */}
      <Card>
        <CardHeader>
          <CardTitle className="font-mono text-base">{job.code}</CardTitle>
          <CardDescription>{job.task_name}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm">{job.description ?? "—"}</p>
        </CardContent>
      </Card>

      {/* Edit form */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("editTitle")}</CardTitle>
          <CardDescription>{tDetail("editSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
          >
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="cron_expression">{tDetail("cronExpression")}</Label>
                <Input
                  id="cron_expression"
                  className="font-mono"
                  placeholder="* * * * *"
                  {...form.register("cron_expression")}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="queue">{tDetail("queue")}</Label>
                <Input id="queue" {...form.register("queue")} />
              </div>
            </div>

            {cronPreview.length > 0 ? (
              <div className="rounded-md border bg-muted/30 p-3">
                <p className="text-xs font-semibold uppercase text-muted-foreground">
                  {tDetail("cronPreview")}
                </p>
                <ul className="mt-1 list-inside list-disc font-mono text-xs">
                  {cronPreview.map((d) => (
                    <li key={d.toISOString()}>{d.toLocaleString()}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label htmlFor="args">{tDetail("args")}</Label>
              <textarea
                id="args"
                className="font-mono text-xs flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                {...form.register("argsJson")}
              />
              {form.formState.errors.argsJson ? (
                <p className="text-xs text-destructive">
                  {form.formState.errors.argsJson.message}
                </p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="kwargs">{tDetail("kwargs")}</Label>
              <textarea
                id="kwargs"
                className="font-mono text-xs flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                {...form.register("kwargsJson")}
              />
              {form.formState.errors.kwargsJson ? (
                <p className="text-xs text-destructive">
                  {form.formState.errors.kwargsJson.message}
                </p>
              ) : null}
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="enabled"
                {...form.register("enabled")}
                className="h-4 w-4"
              />
              <Label htmlFor="enabled" className="cursor-pointer">
                {tDetail("enabled")}
              </Label>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <RbacGuard permissions={["jobs:run"]}>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setConfirmRun(true)}
                  disabled={runNow.isPending}
                >
                  <Play className="h-4 w-4" /> {tDetail("runNow")}
                </Button>
              </RbacGuard>
              <RbacGuard permissions={["jobs:write"]}>
                <Button type="submit" disabled={update.isPending}>
                  {update.isPending ? tCommon("loading") : tCommon("save")}
                </Button>
              </RbacGuard>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Runs history */}
      <Card>
        <CardHeader>
          <CardTitle>{tDetail("runsTitle")}</CardTitle>
          <CardDescription>{tDetail("runsSubtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {!runsPage || runsPage.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">{tDetail("noRuns")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{tDetail("startedAt")}</TableHead>
                  <TableHead>{tDetail("finishedAt")}</TableHead>
                  <TableHead>{tDetail("status")}</TableHead>
                  <TableHead>{tDetail("durationMs")}</TableHead>
                  <TableHead>{tDetail("error")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runsPage.items.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="text-xs">
                      {r.started_at
                        ? new Date(r.started_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {r.finished_at
                        ? new Date(r.finished_at).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {r.duration_ms ?? "—"}
                    </TableCell>
                    <TableCell className="max-w-md truncate text-xs text-destructive">
                      {r.error ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Audit timeline */}
      <RbacGuard permissions={["audit:read"]}>
        <Card>
          <CardHeader>
            <CardTitle>{tDetail("auditTitle")}</CardTitle>
            <CardDescription>{tDetail("auditSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            <AuditTimeline entityType="job" entityId={jobId} />
          </CardContent>
        </Card>
      </RbacGuard>

      <ConfirmDialog
        open={confirmRun}
        onOpenChange={setConfirmRun}
        title={tDetail("confirmRunTitle")}
        description={tDetail("confirmRunDesc")}
        confirmLabel={tDetail("runNow")}
        busy={runNow.isPending}
        onConfirm={handleRunNow}
      />
    </div>
  );
}
