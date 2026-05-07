"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateJob } from "@/lib/hooks/jobs/use-jobs";
import type { JobOwner, ScheduleType } from "@/lib/api/endpoints/jobs";

export function CreateJobClient() {
  const t = useTranslations("admin.jobs.create");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const createJob = useCreateJob();

  const schema = React.useMemo(
    () =>
      z
        .object({
          code: z.string().min(2).max(128),
          task_name: z.string().min(2).max(200),
          description: z.string().max(500).optional(),
          owner: z.enum(["infra", "business"]),
          schedule_type: z.enum(["cron", "interval"]),
          cron_expression: z.string().optional(),
          interval_seconds: z.coerce.number().int().positive().optional(),
          timezone: z.string().min(2).max(64),
          queue: z.string().min(1).max(64),
          enabled: z.boolean(),
        })
        .refine(
          (v) =>
            (v.schedule_type === "cron" && !!v.cron_expression) ||
            (v.schedule_type === "interval" && !!v.interval_seconds),
          {
            message: t("errors.scheduleRequired"),
            path: ["cron_expression"],
          },
        ),
    [t],
  );
  type Values = z.infer<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: "",
      task_name: "",
      description: "",
      owner: "infra",
      schedule_type: "cron",
      cron_expression: "",
      timezone: "Asia/Dubai",
      queue: "default",
      enabled: true,
    },
    mode: "onBlur",
  });

  const scheduleType = form.watch("schedule_type");

  const onSubmit = async (values: Values) => {
    try {
      const created = await createJob.mutateAsync({
        code: values.code,
        task_name: values.task_name,
        description: values.description || null,
        owner: values.owner,
        schedule_type: values.schedule_type,
        cron_expression:
          values.schedule_type === "cron"
            ? (values.cron_expression ?? null)
            : null,
        interval_seconds:
          values.schedule_type === "interval"
            ? (values.interval_seconds ?? 60)
            : null,
        timezone: values.timezone,
        queue: values.queue,
        args: [],
        kwargs: {},
        enabled: values.enabled,
      });
      toast.success(t("success"));
      router.push(`/admin/jobs/${created.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.failed"));
    }
  };

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>{t("formTitle")}</CardTitle>
        <CardDescription>{t("formSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(onSubmit)}
          noValidate
        >
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="code">{t("code")}</Label>
              <Input id="code" className="font-mono" {...form.register("code")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="task_name">{t("taskName")}</Label>
              <Input
                id="task_name"
                className="font-mono"
                {...form.register("task_name")}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">{t("description")}</Label>
            <Input id="description" {...form.register("description")} />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-1.5">
              <Label>{t("owner")}</Label>
              <Select
                value={form.watch("owner")}
                onValueChange={(v) =>
                  form.setValue("owner", v as JobOwner, { shouldValidate: true })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="infra">infra</SelectItem>
                  <SelectItem value="business">business</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>{t("scheduleType")}</Label>
              <Select
                value={form.watch("schedule_type")}
                onValueChange={(v) =>
                  form.setValue("schedule_type", v as ScheduleType, {
                    shouldValidate: true,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cron">cron</SelectItem>
                  <SelectItem value="interval">interval</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="queue">{t("queue")}</Label>
              <Input id="queue" {...form.register("queue")} />
            </div>
          </div>

          {scheduleType === "cron" ? (
            <div className="space-y-1.5">
              <Label htmlFor="cron_expression">{t("cronExpression")}</Label>
              <Input
                id="cron_expression"
                className="font-mono"
                placeholder="0 */6 * * *"
                {...form.register("cron_expression")}
              />
              {form.formState.errors.cron_expression ? (
                <p className="text-xs text-destructive">
                  {form.formState.errors.cron_expression.message}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label htmlFor="interval_seconds">{t("intervalSeconds")}</Label>
              <Input
                id="interval_seconds"
                type="number"
                min={1}
                {...form.register("interval_seconds", { valueAsNumber: true })}
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="timezone">{t("timezone")}</Label>
            <Input id="timezone" {...form.register("timezone")} />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled"
              {...form.register("enabled")}
              className="h-4 w-4"
            />
            <Label htmlFor="enabled" className="cursor-pointer">
              {t("enabled")}
            </Label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/admin/jobs")}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={createJob.isPending}>
              {createJob.isPending ? tCommon("loading") : t("submit")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
