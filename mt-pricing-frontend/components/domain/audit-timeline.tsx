"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { ChevronDown, ChevronRight, History, User as UserIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils/cn";
import { flattenEvents, useAuditEvents } from "@/lib/hooks/audit/use-audit";
import type { AuditEvent } from "@/lib/api/endpoints/audit";

interface Props {
  entityType: string;
  entityId: string;
  /** Page size por request al backend. Backend cap = 100. */
  pageSize?: number;
  className?: string;
}

/**
 * Timeline reutilizable de audit events para una entidad concreta.
 *
 * Consumo:
 *   <AuditTimeline entityType="product" entityId={sku} />
 *   <AuditTimeline entityType="user"    entityId={userId} />
 *   <AuditTimeline entityType="job"     entityId={jobId} />
 */
export function AuditTimeline({
  entityType,
  entityId,
  pageSize = 50,
  className,
}: Props) {
  const t = useTranslations("audit");
  const query = useAuditEvents({
    entity_type: entityType,
    entity_id: entityId,
    limit: pageSize,
  });

  if (query.isLoading) {
    return (
      <div className={cn("space-y-3", className)}>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
        {t("loadError")}
      </div>
    );
  }

  const events = flattenEvents(query.data);

  if (events.length === 0) {
    return (
      <div className="rounded-md border border-dashed bg-muted/30 p-6 text-center text-sm text-muted-foreground">
        <History className="mx-auto mb-2 h-6 w-6 opacity-60" aria-hidden />
        {t("empty")}
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      <ol className="relative space-y-3 border-l border-border pl-5">
        {events.map((evt) => (
          <AuditEventCard key={evt.id} event={evt} />
        ))}
      </ol>
      {query.hasNextPage ? (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={query.isFetchingNextPage}
            onClick={() => {
              void query.fetchNextPage();
            }}
          >
            {query.isFetchingNextPage ? t("loading") : t("loadMore")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function AuditEventCard({ event }: { event: AuditEvent }) {
  const t = useTranslations("audit");
  const [expanded, setExpanded] = React.useState(false);

  const ts = new Date(event.event_at);
  const actorLabel =
    event.actor?.full_name ??
    event.actor?.email ??
    (event.actor === null ? t("system") : "—");
  const hasDiff =
    event.payload_diff && Object.keys(event.payload_diff).length > 0;
  const hasBeforeAfter = event.before !== null || event.after !== null;
  const expandable = hasDiff || hasBeforeAfter;

  return (
    <li className="relative">
      <span
        className="absolute -left-[27px] top-2 h-3 w-3 rounded-full border-2 border-background bg-primary"
        aria-hidden
      />
      <div className="rounded-md border bg-card p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Badge variant="secondary" className="font-mono text-[11px]">
            {event.action}
          </Badge>
          <Badge variant="outline" className="text-[11px]">
            {event.entity_type}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {ts.toLocaleString()}
          </span>
        </div>
        <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          <UserIcon className="h-3.5 w-3.5" aria-hidden />
          <span className="truncate">{actorLabel}</span>
          {event.request_id ? (
            <span className="font-mono text-[10px] opacity-60">
              · req {event.request_id.slice(0, 8)}
            </span>
          ) : null}
        </div>
        {event.reason ? (
          <p className="mt-2 text-xs italic text-muted-foreground">
            “{event.reason}”
          </p>
        ) : null}
        {expandable ? (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              aria-expanded={expanded}
            >
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              {expanded ? t("hideDiff") : t("showDiff")}
            </button>
            {expanded ? (
              <div className="mt-2 space-y-2">
                {hasDiff ? (
                  <DiffViewer label={t("diff")} value={event.payload_diff} />
                ) : null}
                {event.before ? (
                  <DiffViewer label={t("before")} value={event.before} />
                ) : null}
                {event.after ? (
                  <DiffViewer label={t("after")} value={event.after} />
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}

function DiffViewer({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown> | null;
}) {
  if (!value) return null;
  return (
    <details className="rounded-md border bg-muted/30 p-2">
      <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
        {label}
      </summary>
      <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-snug">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
