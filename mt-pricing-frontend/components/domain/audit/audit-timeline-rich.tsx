"use client";

import * as React from "react";
import { History, User as UserIcon } from "lucide-react";

import {
  MtButton,
  Pill,
  SectionCard,
} from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { AuditDiffViewer } from "@/components/domain/audit/audit-diff-viewer";
import {
  flattenAuditEvents,
  useAuditEventsQuery,
} from "@/lib/hooks/audit/use-audit-query";
import type {
  AuditEvent,
  AuditQueryFilters,
} from "@/lib/api/endpoints/audit-query";

interface Props {
  baseFilters: AuditQueryFilters;
  /** Si `true`, agrupa por día (yyyy-mm-dd). Default `true`. */
  groupByDay?: boolean;
  pageSize?: number;
  className?: string;
}

/**
 * Timeline rica con grouping por día y diff inline.
 *
 * Extensión sobre `audit-timeline.tsx` (S1.5) que sólo lista eventos planos.
 * Esta variante:
 *  - Agrupa por día (header sticky con fecha localizada).
 *  - Cada evento expande con `AuditDiffViewer`.
 *  - Filtros se delegan al `baseFilters` recibido — la timeline no expone
 *    UI propia (la tabla `AuditTable` ya lo hace).
 */
export function AuditTimelineRich({
  baseFilters,
  groupByDay = true,
  pageSize = 50,
  className,
}: Props) {
  const filters = React.useMemo<AuditQueryFilters>(
    () => ({ ...baseFilters, limit: pageSize }),
    [baseFilters, pageSize],
  );
  const query = useAuditEventsQuery(filters);

  if (query.isLoading) {
    return (
      <div className={`space-y-2 ${className ?? ""}`}>
        <MtSkeleton width="100%" height={50} />
        <MtSkeleton width="100%" height={50} />
        <MtSkeleton width="100%" height={50} />
      </div>
    );
  }

  if (query.isError) {
    return (
      <MtError
        message="No se pudo cargar la timeline."
        onRetry={() => void query.refetch()}
      />
    );
  }

  const events = flattenAuditEvents(query.data);

  if (events.length === 0) {
    return (
      <SectionCard {...(className ? { className } : {})}>
        <MtEmpty
          title="Sin eventos"
          hint="Aún no hay actividad registrada."
          icon={<History className="size-6" strokeWidth={1.4} />}
        />
      </SectionCard>
    );
  }

  const groups = groupByDay ? groupEventsByDay(events) : [{ day: null, events }];

  return (
    <SectionCard {...(className ? { className } : {})}>
      <ol
        className="divide-y"
        style={{ borderColor: MT.border }}
      >
        {groups.map((g) => (
          <li key={g.day ?? "all"} className="px-4 py-3">
            {g.day ? (
              <div
                className="mt-mono pb-2 text-[10.5px] uppercase tracking-[0.5px]"
                style={{ color: MT.ink3 }}
              >
                {g.day}
              </div>
            ) : null}
            <ol
              className="relative space-y-2 border-l pl-5"
              style={{ borderColor: MT.border }}
            >
              {g.events.map((evt) => (
                <RichEventCard key={evt.id} event={evt} />
              ))}
            </ol>
          </li>
        ))}
      </ol>
      {query.hasNextPage ? (
        <div
          className="flex justify-center border-t px-4 py-3"
          style={{ borderColor: MT.border }}
        >
          <MtButton
            size="sm"
            tone="ghost"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? "Cargando…" : "Cargar más"}
          </MtButton>
        </div>
      ) : null}
    </SectionCard>
  );
}

function RichEventCard({ event }: { event: AuditEvent }) {
  const [open, setOpen] = React.useState(false);
  const ts = new Date(event.event_at);
  const actorLabel = event.actor?.full_name ?? event.actor?.email ?? "Sistema";
  const hasDiff =
    event.payload_diff && Object.keys(event.payload_diff).length > 0;
  const hasBeforeAfter = event.before !== null || event.after !== null;
  const expandable = hasDiff || hasBeforeAfter;

  return (
    <li className="relative">
      <span
        className="absolute -left-[26px] top-2 h-2.5 w-2.5 rounded-full border-2"
        style={{
          background: MT.brand,
          borderColor: MT.surface,
        }}
        aria-hidden
      />
      <div
        className="rounded-md border p-2.5"
        style={{ borderColor: MT.border, backgroundColor: MT.surface }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="brand" mono>
            {event.action}
          </Pill>
          <Pill tone="neutral" mono>
            {event.entity_type}
          </Pill>
          <span
            className="mt-mono text-[11px]"
            style={{ color: MT.ink3 }}
          >
            {ts.toLocaleTimeString()}
          </span>
        </div>
        <div
          className="mt-1 flex items-center gap-1.5 text-[11px]"
          style={{ color: MT.ink3 }}
        >
          <UserIcon className="size-3" />
          <span>{actorLabel}</span>
        </div>
        {event.reason ? (
          <p
            className="mt-1 text-[12px] italic"
            style={{ color: MT.ink3 }}
          >
            &ldquo;{event.reason}&rdquo;
          </p>
        ) : null}
        {expandable ? (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
              style={{ color: MT.brand }}
              aria-expanded={open}
            >
              {open ? "Ocultar diff" : "Ver diff"}
            </button>
            {open ? (
              <div className="mt-2">
                <AuditDiffViewer
                  before={event.before}
                  after={event.after}
                  diff={event.payload_diff ?? null}
                />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}

function groupEventsByDay(events: AuditEvent[]): Array<{
  day: string | null;
  events: AuditEvent[];
}> {
  const fmt = new Intl.DateTimeFormat("es-ES", {
    weekday: "long",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const out = new Map<string, AuditEvent[]>();
  for (const evt of events) {
    const key = fmt.format(new Date(evt.event_at));
    const arr = out.get(key);
    if (arr) arr.push(evt);
    else out.set(key, [evt]);
  }
  return Array.from(out.entries()).map(([day, evts]) => ({
    day,
    events: evts,
  }));
}
