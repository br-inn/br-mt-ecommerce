"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Loader2, Play, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { useScrapeRun, useScraperJob } from "@/lib/hooks/admin/use-scraper";
import type { ScrapeJobStatusValue } from "@/lib/api/endpoints/scraper";

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: ScrapeJobStatusValue }) {
  const t = useTranslations("admin.scraper.job.statuses");

  const variant = ((): "default" | "secondary" | "destructive" | "outline" => {
    switch (status) {
      case "completed":
        return "default";
      case "failed":
        return "destructive";
      case "running":
        return "secondary";
      default:
        return "outline";
    }
  })();

  return (
    <Badge variant={variant} className="gap-1.5">
      {status === "running" ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : null}
      {t(status)}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Main client component
// ---------------------------------------------------------------------------

export function AdminScraperClient() {
  const t = useTranslations("admin.scraper");
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("products:write");
  const router = useRouter();
  const searchParams = useSearchParams();

  // Form state
  const [skusRaw, setSkusRaw] = React.useState("");
  const [allProducts, setAllProducts] = React.useState(false);
  const [force, setForce] = React.useState(false);

  // Active job — persisted in URL so it survives navigation
  const [jobId, setJobId] = React.useState<string | null>(
    () => searchParams.get("job"),
  );

  const run = useScrapeRun();
  const { data: jobStatus, isError: jobError } = useScraperJob(jobId);

  // Parse SKU textarea into an array
  function parseSkus(raw: string): string[] {
    return raw
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const skus = allProducts ? [] : parseSkus(skusRaw);
    try {
      const resp = await run.mutateAsync({ skus, force });
      setJobId(resp.job_id);
      router.replace(`?job=${encodeURIComponent(resp.job_id)}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.runFailed"));
    }
  };

  const handleReset = () => {
    setJobId(null);
    router.replace("?");
    run.reset();
    setSkusRaw("");
    setForce(false);
    setAllProducts(false);
  };

  const isRunning = jobStatus?.status === "pending" || jobStatus?.status === "running";

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      {/* ------------------------------------------------------------------ */}
      {/* Run section                                                          */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <CardTitle>{t("run.title")}</CardTitle>
          <CardDescription>{t("description")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {/* All-products toggle */}
            <div className="flex items-center gap-2">
              <Checkbox
                id="allProducts"
                checked={allProducts}
                onCheckedChange={(v) => setAllProducts(v === true)}
                disabled={!canWrite || run.isPending || isRunning}
              />
              <Label htmlFor="allProducts" className="cursor-pointer font-normal">
                {t("run.allProducts")}
              </Label>
            </div>

            {/* SKU list textarea (hidden when allProducts) */}
            {!allProducts ? (
              <div className="space-y-1.5">
                <Label htmlFor="skus">{t("run.skusLabel")}</Label>
                <Textarea
                  id="skus"
                  rows={6}
                  placeholder={t("run.skusPlaceholder")}
                  value={skusRaw}
                  onChange={(e) => setSkusRaw(e.target.value)}
                  disabled={!canWrite || run.isPending || isRunning}
                  className="font-mono text-xs"
                />
              </div>
            ) : null}

            {/* Force re-scan */}
            <div className="flex items-center gap-2">
              <Checkbox
                id="force"
                checked={force}
                onCheckedChange={(v) => setForce(v === true)}
                disabled={!canWrite || run.isPending || isRunning}
              />
              <Label htmlFor="force" className="cursor-pointer font-normal">
                {t("run.force")}
              </Label>
            </div>

            <Button
              type="submit"
              className="w-full gap-2"
              disabled={!canWrite || run.isPending || isRunning}
              data-testid="scraper-run-submit"
            >
              {run.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {t("run.submitting")}
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  {t("run.submit")}
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Job status section                                                   */}
      {/* ------------------------------------------------------------------ */}
      {jobId ? (
        <Card className="self-start">
          <CardHeader>
            <CardTitle>{t("job.title")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Job ID */}
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t("job.id")}
              </p>
              <p className="font-mono text-xs break-all">{jobId}</p>
            </div>

            {jobError ? (
              <p className="text-sm text-destructive">{t("errors.jobFailed")}</p>
            ) : jobStatus ? (
              <>
                {/* Status */}
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Estado
                  </p>
                  <StatusBadge status={jobStatus.status} />
                </div>

                {/* Progress */}
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    {t("job.progress")}
                  </p>
                  <p className="text-sm">
                    {jobStatus.completed} / {jobStatus.total} SKUs
                    {jobStatus.failed > 0 ? (
                      <span className="ml-2 text-destructive">
                        ({jobStatus.failed} fallidos)
                      </span>
                    ) : null}
                  </p>

                  {/* Progress bar */}
                  {jobStatus.total > 0 ? (
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{
                          width: `${Math.round((jobStatus.completed / jobStatus.total) * 100)}%`,
                        }}
                      />
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Consultando estado…
              </div>
            )}

            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full gap-2"
              onClick={handleReset}
              disabled={isRunning}
            >
              <RotateCcw className="h-4 w-4" />
              {t("job.newScan")}
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
