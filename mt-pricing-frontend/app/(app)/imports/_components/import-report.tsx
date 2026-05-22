"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { CheckCircle2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ImportRun } from "@/lib/api/endpoints/imports";
import { ReconciliationPanel } from "./reconciliation-panel";

interface Props {
  run: ImportRun;
  onReset: () => void;
}

export function ImportReportPanel({ run, onReset }: Props) {
  const t = useTranslations("imports.report");
  const tCommon = useTranslations("common");
  const summary = run.summary;
  const isOk = run.status === "completed";

  return (
    <Card data-testid="import-report">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isOk ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-hidden />
          ) : (
            <AlertTriangle className="h-5 w-5 text-destructive" aria-hidden />
          )}
          {isOk ? t("titleSuccess") : t("titleFailed")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {summary ? (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label={t("creates")} value={summary.creates} />
            <Stat label={t("updates")} value={summary.updates} />
            <Stat label={t("skipped")} value={summary.skipped_locked + summary.no_change} />
            <Stat label={t("errors")} value={summary.errors + summary.orphans} />
          </dl>
        ) : null}

        {run.reconciliation ? (
          <ReconciliationPanel reconciliation={run.reconciliation} />
        ) : null}

        <div className="flex items-center justify-between gap-2">
          <Button variant="ghost" onClick={onReset} data-testid="import-reset">
            {t("newImport")}
          </Button>
          <Button asChild>
            <Link href="/products">{t("goProducts")}</Link>
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          run_id: <span className="font-mono">{run.run_id}</span>
          {" · "}
          {tCommon("close")}
        </p>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-2xl font-semibold">{value}</dd>
    </div>
  );
}
