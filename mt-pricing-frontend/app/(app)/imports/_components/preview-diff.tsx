"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  ImportPreview,
  ImportRow,
} from "@/lib/api/endpoints/imports";

interface Props {
  preview: ImportPreview;
  onConfirm: () => void;
  onBack: () => void;
  isApplying?: boolean;
}

type TabKey = "creates" | "updates" | "skipped" | "errors";

function rowsByAction(rows: ImportRow[]): Record<TabKey, ImportRow[]> {
  return {
    creates: rows.filter((r) => r.action === "create"),
    updates: rows.filter((r) => r.action === "update"),
    skipped: rows.filter((r) => r.action === "skip_locked" || r.action === "no_change"),
    errors: rows.filter((r) => r.action === "error" || r.action === "orphan"),
  };
}

/** Step 2 + 3: tabla diff con tabs por categoría + botón confirmar. */
export function PreviewDiff({ preview, onConfirm, onBack, isApplying }: Props) {
  const t = useTranslations("imports.preview");
  const tCommon = useTranslations("common");
  const summary = preview.summary;
  const buckets = React.useMemo(
    () => rowsByAction(preview.rows ?? []),
    [preview.rows],
  );

  return (
    <div className="space-y-4" data-testid="import-preview">
      <div className="grid gap-3 sm:grid-cols-4" data-testid="import-summary">
        <SummaryCard
          label={t("summary.creates")}
          value={summary?.creates ?? 0}
          tone="positive"
        />
        <SummaryCard
          label={t("summary.updates")}
          value={summary?.updates ?? 0}
          tone="info"
        />
        <SummaryCard
          label={t("summary.skipped")}
          value={(summary?.skipped_locked ?? 0) + (summary?.no_change ?? 0)}
          tone="muted"
        />
        <SummaryCard
          label={t("summary.errors")}
          value={(summary?.errors ?? 0) + (summary?.orphans ?? 0)}
          tone="destructive"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="creates">
            <TabsList>
              <TabsTrigger value="creates" data-testid="tab-creates">
                {t("tabs.creates")} ({buckets.creates.length})
              </TabsTrigger>
              <TabsTrigger value="updates" data-testid="tab-updates">
                {t("tabs.updates")} ({buckets.updates.length})
              </TabsTrigger>
              <TabsTrigger value="skipped" data-testid="tab-skipped">
                {t("tabs.skipped")} ({buckets.skipped.length})
              </TabsTrigger>
              <TabsTrigger value="errors" data-testid="tab-errors">
                {t("tabs.errors")} ({buckets.errors.length})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="creates">
              <SimpleRowsTable rows={buckets.creates} kind="creates" />
            </TabsContent>
            <TabsContent value="updates">
              <DiffRowsTable rows={buckets.updates} />
            </TabsContent>
            <TabsContent value="skipped">
              <SimpleRowsTable rows={buckets.skipped} kind="skipped" />
            </TabsContent>
            <TabsContent value="errors">
              <ErrorsTable rows={buckets.errors} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack} disabled={isApplying}>
          {tCommon("back")}
        </Button>
        <Button
          onClick={onConfirm}
          disabled={isApplying}
          data-testid="import-confirm"
        >
          {isApplying ? tCommon("loading") : t("confirm")}
        </Button>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "positive" | "info" | "muted" | "destructive";
}) {
  const colors: Record<typeof tone, string> = {
    positive: "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-400",
    info: "border-blue-500/30 bg-blue-500/5 text-blue-700 dark:text-blue-400",
    muted: "border-muted-foreground/20 bg-muted/40 text-muted-foreground",
    destructive: "border-destructive/30 bg-destructive/5 text-destructive",
  };
  return (
    <div className={`rounded-md border p-3 ${colors[tone]}`}>
      <p className="text-xs uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
}

function SimpleRowsTable({
  rows,
  kind,
}: {
  rows: ImportRow[];
  kind: "creates" | "skipped";
}) {
  if (rows.length === 0) {
    return <EmptyRow />;
  }
  return (
    <div className="max-h-96 overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">#</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow
              key={`${kind}-${r.row_index}-${r.sku}`}
              data-testid={`row-${kind}-${r.sku}`}
            >
              <TableCell className="text-muted-foreground">{r.row_index}</TableCell>
              <TableCell className="font-mono text-xs">{r.sku}</TableCell>
              <TableCell>
                <Badge variant="outline" className="capitalize">
                  {r.action.replace("_", " ")}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function DiffRowsTable({ rows }: { rows: ImportRow[] }) {
  if (rows.length === 0) return <EmptyRow />;
  return (
    <div className="max-h-96 overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">#</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Field</TableHead>
            <TableHead>Before</TableHead>
            <TableHead>After</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.flatMap((r) =>
            (r.diff ?? []).map((d, i) => (
              <TableRow key={`u-${r.row_index}-${d.field}-${i}`}>
                <TableCell className="text-muted-foreground">
                  {r.row_index}
                </TableCell>
                <TableCell className="font-mono text-xs">{r.sku}</TableCell>
                <TableCell>
                  <span className="font-mono text-xs">{d.field}</span>
                  {d.locked ? (
                    <Badge variant="outline" className="ml-2">
                      locked
                    </Badge>
                  ) : null}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground line-through">
                  {String(d.before ?? "—")}
                </TableCell>
                <TableCell className="text-xs font-medium">
                  {String(d.after ?? "—")}
                </TableCell>
              </TableRow>
            )),
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function ErrorsTable({ rows }: { rows: ImportRow[] }) {
  if (rows.length === 0) return <EmptyRow />;
  return (
    <div className="max-h-96 overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-16">#</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Code</TableHead>
            <TableHead>Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={`e-${r.row_index}-${r.sku}`}>
              <TableCell className="text-muted-foreground">{r.row_index}</TableCell>
              <TableCell className="font-mono text-xs">{r.sku || "—"}</TableCell>
              <TableCell>
                <Badge variant="destructive">{r.error_code ?? "ERR"}</Badge>
              </TableCell>
              <TableCell className="text-xs">{r.error_message ?? "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function EmptyRow() {
  const t = useTranslations("imports.preview");
  return (
    <p className="px-4 py-8 text-center text-sm text-muted-foreground">
      {t("emptyBucket")}
    </p>
  );
}
