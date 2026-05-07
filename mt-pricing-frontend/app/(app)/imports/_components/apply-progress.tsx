"use client";

import { useTranslations } from "next-intl";
import { Loader2, AlertTriangle, CheckCircle2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ImportRun } from "@/lib/api/endpoints/imports";

interface Props {
  run: ImportRun | undefined;
  isLoading: boolean;
}

/** Step 4 (parte streaming): muestra status + progress bar mientras backend aplica. */
export function ApplyProgress({ run, isLoading }: Props) {
  const t = useTranslations("imports.apply");

  if (isLoading || !run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> {t("starting")}
          </CardTitle>
        </CardHeader>
      </Card>
    );
  }

  const progress = run.progress;
  const pct =
    progress && progress.chunks_total > 0
      ? Math.min(100, Math.round((progress.chunks_done / progress.chunks_total) * 100))
      : run.status === "completed"
        ? 100
        : 0;

  const Icon =
    run.status === "completed"
      ? CheckCircle2
      : run.status === "failed" || run.status === "cancelled"
        ? AlertTriangle
        : Loader2;

  const iconClass =
    run.status === "completed"
      ? "h-4 w-4 text-emerald-600"
      : run.status === "failed" || run.status === "cancelled"
        ? "h-4 w-4 text-destructive"
        : "h-4 w-4 animate-spin";

  return (
    <Card data-testid="import-apply-progress">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className={iconClass} aria-hidden />
          {t(`status.${run.status}`)}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            data-testid="import-progress-bar"
          >
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {progress
              ? t("chunks", {
                  done: progress.chunks_done,
                  total: progress.chunks_total,
                })
              : t("waiting")}
            {progress && progress.rows_done > 0
              ? ` · ${t("rowsDone", { count: progress.rows_done })}`
              : null}
          </p>
        </div>
        {run.error_message ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            {run.error_message}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
