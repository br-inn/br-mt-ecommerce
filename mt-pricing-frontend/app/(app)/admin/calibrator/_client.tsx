"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Play } from "lucide-react";

import { CalibratorVersionCard } from "@/components/admin/calibrator-version-card";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useCalibratorActive,
  useTrainCalibrator,
} from "@/lib/hooks/admin/use-calibrator";
import { usePermissions } from "@/lib/hooks/use-permissions";

const VERSION_RE = /^v\d+(\.\d+)*$/;

export function AdminCalibratorClient() {
  const t = useTranslations("admin.calibrator");
  const tCommon = useTranslations("common");
  const { hasPermission } = usePermissions();
  const canTrain = hasPermission("admin:calibrator:train");
  const canPromote = hasPermission("admin:calibrator:promote");

  const { data, isLoading, isError, refetch } = useCalibratorActive();
  const train = useTrainCalibrator();

  const schema = React.useMemo(
    () =>
      z.object({
        dataset_path: z.string().min(1, t("errors.datasetPathRequired")),
        version: z
          .string()
          .min(2, t("errors.versionRequired"))
          .regex(VERSION_RE, t("errors.versionFormat")),
      }),
    [t],
  );
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      dataset_path: "data/golden_labels_v2.csv",
      version: "",
    },
    mode: "onBlur",
  });

  const onSubmit = async (values: Values) => {
    try {
      const resp = await train.mutateAsync(values);
      toast.success(t("toast.trainQueued", { task: resp.task_id }));
      form.reset({ dataset_path: values.dataset_path, version: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.trainFailed"));
    }
  };

  const versions = data?.versions ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("activeTitle")}</CardTitle>
            <CardDescription>{t("activeSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <MtSkeleton height={120} className="w-full" />
            ) : isError ? (
              <MtError
                message={t("errors.loadFailed")}
                onRetry={() => void refetch()}
              />
            ) : data?.active ? (
              <CalibratorVersionCard
                version={data.active}
                canPromote={canPromote}
              />
            ) : (
              <MtEmpty
                title={t("empty.activeTitle")}
                hint={t("empty.activeHint")}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("versionsTitle")}</CardTitle>
            <CardDescription>{t("versionsSubtitle")}</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 2 }).map((_, i) => (
                  <MtSkeleton key={i} height={120} className="w-full" />
                ))}
              </div>
            ) : versions.length === 0 ? (
              <MtEmpty
                title={t("empty.versionsTitle")}
                hint={t("empty.versionsHint")}
              />
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {versions.map((v) => (
                  <CalibratorVersionCard
                    key={v.version}
                    version={v}
                    canPromote={canPromote}
                  />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="self-start">
        <CardHeader>
          <CardTitle>{t("train.title")}</CardTitle>
          <CardDescription>{t("train.subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            noValidate
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <Label htmlFor="dataset_path">{t("train.datasetPath")}</Label>
              <Input
                id="dataset_path"
                {...form.register("dataset_path")}
                placeholder="data/golden_labels_v2.csv"
                disabled={!canTrain}
                className="font-mono text-xs"
              />
              {form.formState.errors.dataset_path ? (
                <p className="text-xs text-destructive">
                  {form.formState.errors.dataset_path.message}
                </p>
              ) : null}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="version">{t("train.version")}</Label>
              <Input
                id="version"
                {...form.register("version")}
                placeholder="v3"
                disabled={!canTrain}
                className="font-mono text-xs"
              />
              {form.formState.errors.version ? (
                <p className="text-xs text-destructive">
                  {form.formState.errors.version.message}
                </p>
              ) : null}
            </div>
            <Button
              type="submit"
              className="w-full gap-2"
              disabled={!canTrain || train.isPending}
              data-testid="calibrator-train-submit"
            >
              <Play className="h-4 w-4" />
              {train.isPending ? tCommon("loading") : t("train.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
