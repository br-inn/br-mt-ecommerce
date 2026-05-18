"use client";

import * as React from "react";
import { ChevronDown, ChevronRight, History } from "lucide-react";

import {
  FilterChip,
  MtButton,
  MtTd,
  MtTh,
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
  /** Filtros base aplicados (e.g. `entity_id` del SKU). */
  baseFilters: AuditQueryFilters;
  /** Multi-entity_type chips disponibles en la toolbar. */
  entityTypes?: string[];
  pageSize?: number | undefined;
  className?: string;
}

const DEFAULT_ENTITIES = [
  "products",
  "costs",
  "prices",
  "product_translations",
  "fx_rates",
];

/**
 * Tabla de audit_events con filtros multi-entidad + diff viewer expandible.
 *
 * UX:
 *  - Toolbar: chips por entity_type (toggle multi-select), search por actor,
 *    rango fechas (from/to).
 *  - Tabla densa: timestamp · actor · entity · action · summary diff.
 *  - Click en fila → expand inline con `AuditDiffViewer`.
 *  - Paginación cursor con "Cargar más" al final.
 */
export function AuditTable({
  baseFilters,
  entityTypes = DEFAULT_ENTITIES,
  pageSize = 50,
  className,
}: Props) {
  const [selectedEntities, setSelectedEntities] = React.useState<string[]>(
    () => entityTypes,
  );
  const [actorEmail, setActorEmail] = React.useState("");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");

  const filters = React.useMemo<AuditQueryFilters>(() => {
    // Solo enviar entity_types cuando el usuario ha acotado la selección.
    // Si todos los chips están activos (selección completa) no se filtra por
    // tipo para que el fan-out del backend devuelva todas las entidades.
    const isSubset =
      selectedEntities.length > 0 &&
      selectedEntities.length < entityTypes.length;
    const f: AuditQueryFilters = {
      ...baseFilters,
      ...(isSubset ? { entity_types: selectedEntities } : {}),
      ...(actorEmail ? { actor_email: actorEmail } : {}),
      ...(from ? { from } : {}),
      ...(to ? { to } : {}),
      limit: pageSize,
    };
    return f;
  }, [baseFilters, selectedEntities, entityTypes.length, actorEmail, from, to, pageSize]);

  const query = useAuditEventsQuery(filters);

  const toggleEntity = (e: string) => {
    setSelectedEntities((prev) =>
      prev.includes(e) ? prev.filter((x) => x !== e) : [...prev, e],
    );
  };

  return (
    <SectionCard
      title="Histórico de auditoría"
      subtitle="Eventos cronológicos con diff before/after"
      {...(className ? { className } : {})}
      actions={
        <Pill tone="brand" mono>
          {flattenAuditEvents(query.data).length}
        </Pill>
      }
    >
      <div
        className="border-b px-4 py-3"
        style={{ borderColor: MT.border, backgroundColor: MT.surface2 }}
      >
        <div className="flex flex-wrap items-center gap-2">
          {entityTypes.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => toggleEntity(e)}
              className="appearance-none border-0 bg-transparent p-0"
            >
              <FilterChip
                label={e}
                active={selectedEntities.includes(e)}
                tone="brand"
              />
            </button>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
          <Field label="Actor (email)">
            <input
              type="text"
              value={actorEmail}
              onChange={(e) => setActorEmail(e.target.value)}
              placeholder="psierra@br-innovation.com"
              className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
              style={{ borderColor: MT.border }}
            />
          </Field>
          <Field label="Desde">
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
              style={{ borderColor: MT.border }}
            />
          </Field>
          <Field label="Hasta">
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="w-full rounded-[4px] border px-2 py-1 text-[12.5px]"
              style={{ borderColor: MT.border }}
            />
          </Field>
        </div>
      </div>

      <AuditTableBody query={query} />

      {query.hasNextPage ? (
        <div className="flex justify-center border-t px-4 py-3" style={{ borderColor: MT.border }}>
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

function AuditTableBody({
  query,
}: {
  query: ReturnType<typeof useAuditEventsQuery>;
}) {
  if (query.isLoading) {
    return (
      <div className="space-y-2 p-4">
        <MtSkeleton width="100%" height={28} />
        <MtSkeleton width="100%" height={28} />
        <MtSkeleton width="100%" height={28} />
      </div>
    );
  }
  if (query.isError) {
    return (
      <div className="p-4">
        <MtError
          message="No se pudo cargar el histórico de auditoría."
          onRetry={() => void query.refetch()}
        />
      </div>
    );
  }
  const events = flattenAuditEvents(query.data);
  if (events.length === 0) {
    return (
      <MtEmpty
        title="Sin eventos"
        hint="No hay registros para los filtros aplicados."
        icon={<History className="size-6" strokeWidth={1.4} />}
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <MtTh>Timestamp</MtTh>
            <MtTh>Actor</MtTh>
            <MtTh>Entidad</MtTh>
            <MtTh>Acción</MtTh>
            <MtTh className="w-full">Resumen</MtTh>
            <MtTh>—</MtTh>
          </tr>
        </thead>
        <tbody>
          {events.map((evt) => (
            <AuditRow key={evt.id} event={evt} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditRow({
  event,
}: {
  event: AuditEvent;
}) {
  const [open, setOpen] = React.useState(false);
  const ts = new Date(event.event_at);
  const diffCount = event.payload_diff
    ? Object.keys(event.payload_diff).length
    : 0;
  const actorLabel =
    event.actor?.full_name ?? event.actor?.email ?? "Sistema";

  return (
    <>
      <tr
        className="cursor-pointer"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <MtTd mono>{ts.toLocaleString()}</MtTd>
        <MtTd>{actorLabel}</MtTd>
        <MtTd mono>
          <Pill tone="neutral" mono>
            {event.entity_type}
          </Pill>
        </MtTd>
        <MtTd mono>{event.action}</MtTd>
        <MtTd>
          {diffCount > 0 ? (
            <span className="text-[12px]" style={{ color: MT.ink3 }}>
              {diffCount} campo(s) modificado(s)
              {event.reason ? (
                <span className="ml-2 italic">— &ldquo;{event.reason}&rdquo;</span>
              ) : null}
            </span>
          ) : (
            <span style={{ color: MT.ink4 }}>—</span>
          )}
        </MtTd>
        <MtTd>
          {open ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
        </MtTd>
      </tr>
      {open ? (
        <tr>
          <td
            colSpan={6}
            className="border-b px-4 py-3"
            style={{ backgroundColor: MT.surface2, borderColor: MT.border }}
          >
            <AuditDiffViewer
              before={event.before}
              after={event.after}
              diff={event.payload_diff ?? null}
            />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span
        className="mt-mono text-[10.5px] uppercase tracking-[0.5px]"
        style={{ color: MT.ink3 }}
      >
        {label}
      </span>
      {children}
    </label>
  );
}
