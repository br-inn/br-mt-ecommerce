"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { CheckCircle2, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { type CalibratorVersion } from "@/lib/api/endpoints/admin-calibrator";
import { usePromoteCalibrator } from "@/lib/hooks/admin/use-calibrator";

interface Props {
  version: CalibratorVersion;
  canPromote: boolean;
}

function fmtMetric(value: number | null, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

/**
 * Card resumen de una versión del calibrator.
 *
 * - Si `active` muestra badge verde, sin botón promote.
 * - Métricas: ECE, Brier, Log-loss, dataset_size.
 * - Botón "Promote" abre `<ConfirmDialog>` (acción destructiva: cierra
 *   active anterior).
 */
export function CalibratorVersionCard({ version, canPromote }: Props) {
  const t = useTranslations("admin.calibrator");
  const tCommon = useTranslations("common");
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const promote = usePromoteCalibrator();

  const onPromote = async () => {
    try {
      await promote.mutateAsync({ version: version.version });
      toast.success(t("toast.promoted", { version: version.version }));
      setConfirmOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.promoteFailed"));
    }
  };

  return (
    <>
      <div className="flex flex-col gap-3 rounded-md border bg-card p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold">
                {version.version}
              </span>
              {version.active ? (
                <Badge className="gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  {t("active")}
                </Badge>
              ) : null}
            </div>
            <span className="text-xs text-muted-foreground">
              {t("fittedAt")}:{" "}
              {new Date(version.fitted_at).toLocaleString()}
            </span>
            {version.dataset_hash ? (
              <span className="font-mono text-[10px] text-muted-foreground">
                hash: {version.dataset_hash.slice(0, 12)}…
              </span>
            ) : null}
          </div>
          {!version.active ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!canPromote || promote.isPending}
              onClick={() => setConfirmOpen(true)}
              data-testid={`promote-${version.version}`}
            >
              {t("promote")}
            </Button>
          ) : null}
        </div>

        <dl className="grid grid-cols-2 gap-2 border-t pt-3 text-xs sm:grid-cols-4">
          <Metric label="ECE" value={fmtMetric(version.metrics.ece, 4)} />
          <Metric label="Brier" value={fmtMetric(version.metrics.brier, 4)} />
          <Metric
            label="Log-loss"
            value={fmtMetric(version.metrics.log_loss, 4)}
          />
          <Metric
            label={t("datasetSize")}
            value={
              version.metrics.dataset_size === null
                ? "—"
                : version.metrics.dataset_size.toLocaleString()
            }
          />
        </dl>

        {version.artifact_url ? (
          <a
            href={version.artifact_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <ExternalLink className="h-3 w-3" />
            {t("downloadArtifact")}
          </a>
        ) : null}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("confirmPromoteTitle", { version: version.version })}
        description={t("confirmPromoteDesc")}
        confirmLabel={t("promote")}
        cancelLabel={tCommon("cancel")}
        destructive
        busy={promote.isPending}
        onConfirm={onPromote}
      />
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="font-mono text-sm">{value}</dd>
    </div>
  );
}
