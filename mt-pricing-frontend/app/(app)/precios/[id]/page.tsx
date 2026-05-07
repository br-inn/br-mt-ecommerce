/**
 * `/precios/[id]` — detalle de price + history events + acciones (Wave 2).
 */
"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { pricingApi, type PriceStatus } from "@/lib/api/endpoints/pricing";

const TERMINAL: PriceStatus[] = ["exported", "rejected", "superseded"];

export default function PriceDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const t = useTranslations("pricing");
  const queryClient = useQueryClient();

  const [reason, setReason] = React.useState<string>("");
  const [revisedAmount, setRevisedAmount] = React.useState<string>("");

  const { data: price, isLoading, isError } = useQuery({
    queryKey: ["price", id],
    queryFn: () => pricingApi.get(id),
  });

  const onSuccess = () => {
    setReason("");
    setRevisedAmount("");
    queryClient.invalidateQueries({ queryKey: ["price", id] });
    queryClient.invalidateQueries({ queryKey: ["prices"] });
    queryClient.invalidateQueries({ queryKey: ["prices-pending"] });
  };

  const approve = useMutation({
    mutationFn: () => pricingApi.approve(id, reason || undefined),
    onSuccess: () => {
      toast.success(t("actions.approvedToast"));
      onSuccess();
    },
    onError: () => toast.error(t("errors.actionFailed")),
  });

  const reject = useMutation({
    mutationFn: () => {
      if (!reason) throw new Error("reason required");
      return pricingApi.reject(id, reason);
    },
    onSuccess: () => {
      toast.success(t("actions.rejectedToast"));
      onSuccess();
    },
    onError: () => toast.error(t("errors.actionFailed")),
  });

  const revise = useMutation({
    mutationFn: () => {
      if (!revisedAmount || !reason) throw new Error("amount + reason required");
      return pricingApi.revise(id, revisedAmount, reason);
    },
    onSuccess: () => {
      toast.success(t("actions.revisedToast"));
      onSuccess();
    },
    onError: () => toast.error(t("errors.actionFailed")),
  });

  if (isLoading)
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  if (isError || !price)
    return <div className="text-destructive">{t("errors.loadFailed")}</div>;

  const isTerminal = TERMINAL.includes(price.status);

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {price.product_sku}{" "}
            <span className="font-mono text-base text-muted-foreground">
              · {price.scheme_code}
            </span>
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("detail.created")}: {new Date(price.created_at).toLocaleString()}
          </p>
        </div>
        <Badge
          variant={
            (price.status === "approved" || price.status === "auto_approved"
              ? "success"
              : price.status === "rejected"
                ? "destructive"
                : price.status === "pending_review"
                  ? "warning"
                  : "secondary") as never
          }
        >
          {price.status}
        </Badge>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("detail.amounts")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Row label={t("columns.amount")} value={`${price.amount} ${price.currency}`} mono />
            <Row label="PVP_MIN" value={price.pvp_min ?? "—"} mono />
            <Row
              label={t("columns.margin")}
              value={`${(Number(price.margin_pct) * 100).toFixed(2)}%`}
            />
            <Row label={t("columns.rule")} value={price.rule_applied ?? "—"} />
            <Row label={t("detail.formula")} value={price.formula ?? "—"} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("detail.alerts")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {price.alerts.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("detail.noAlerts")}</p>
            )}
            {price.alerts.map((a, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm">
                <Badge
                  variant={
                    (a.severity === "critical"
                      ? "destructive"
                      : a.severity === "warning"
                        ? "warning"
                        : "secondary") as never
                  }
                >
                  {a.severity}
                </Badge>
                <span>
                  <strong>{a.code}</strong> — {a.message}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("detail.breakdown")}</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-auto rounded-md bg-muted p-3 text-xs">
            {JSON.stringify(price.breakdown, null, 2)}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("detail.history")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {price.approval_events.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("detail.noEvents")}
            </p>
          )}
          {price.approval_events.map((e) => (
            <div
              key={e.id}
              className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm"
            >
              <span className="font-mono text-xs text-muted-foreground">
                {new Date(e.created_at).toLocaleString()}
              </span>
              <Badge variant="outline">
                {e.from_status} → {e.to_status}
              </Badge>
              {e.reason && (
                <span className="text-muted-foreground">— {e.reason}</span>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {!isTerminal && (
        <Card>
          <CardHeader>
            <CardTitle>{t("detail.actions")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium">{t("detail.reason")}</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t("detail.reasonPlaceholder")}
                rows={2}
                className="w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => approve.mutate()}
                disabled={approve.isPending}
              >
                {t("actions.approve")}
              </Button>
              <Button
                variant="destructive"
                onClick={() => reject.mutate()}
                disabled={reject.isPending || !reason}
              >
                {t("actions.reject")}
              </Button>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  step="0.01"
                  className="w-32"
                  value={revisedAmount}
                  onChange={(e) => setRevisedAmount(e.target.value)}
                  placeholder={t("detail.newAmount")}
                />
                <Button
                  variant="secondary"
                  onClick={() => revise.mutate()}
                  disabled={revise.isPending || !revisedAmount || !reason}
                >
                  {t("actions.revise")}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono" : ""}>{value}</span>
    </div>
  );
}
