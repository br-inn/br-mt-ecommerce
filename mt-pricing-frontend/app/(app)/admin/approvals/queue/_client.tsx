"use client";

/**
 * ApprovalQueueClient — componente principal de la cola de aprobación.
 *
 * US-1B-02-06 · Pantalla 14 "Cola de aprobación"
 *  - Sticky header con estadísticas
 *  - Filtros rápidos: canal / esquema / fecha
 *  - DataTable con checkboxes y virtual scroll CSS (overflow)
 *  - BulkActionBar sticky inferior
 *  - ApprovalDrawer lateral al click en fila
 */

import * as React from "react";

import { ApprovalDrawer } from "@/components/domain/approvals/ApprovalDrawer";
import { ApprovalTable } from "@/components/domain/approvals/ApprovalTable";
import { BulkActionBar } from "@/components/domain/approvals/BulkActionBar";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { MT } from "@/components/mt/tokens";
import { useApprovalQueue } from "@/lib/hooks/approvals/use-approval-queue";
import { usePermissions } from "@/lib/hooks/use-permissions";
import type { ApprovalQueueFilters } from "@/lib/api/endpoints/approvals";

// ---- Stats header ----------------------------------------------------------

interface StatsHeaderProps {
  total: number | null;
  pending: number;
  isLoading: boolean;
}

function StatsHeader({ total, pending, isLoading }: StatsHeaderProps) {
  return (
    <div
      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-[6px] border px-4 py-3 text-[12px]"
      style={{ background: MT.surface2, borderColor: MT.border }}
    >
      {isLoading ? (
        <MtSkeleton width={320} height={14} />
      ) : (
        <>
          <span style={{ color: MT.ink }}>
            <strong className="mt-mono mt-tnum">{total ?? "—"}</strong>
            <span style={{ color: MT.ink3 }}> total</span>
          </span>
          <span style={{ color: MT.ink4 }}>·</span>
          <span style={{ color: MT.ink }}>
            <strong className="mt-mono mt-tnum">{pending}</strong>
            <span style={{ color: MT.ink3 }}> pendientes</span>
          </span>
        </>
      )}
    </div>
  );
}

// ---- Filter bar ------------------------------------------------------------

interface FilterBarProps {
  filters: ApprovalQueueFilters;
  onFiltersChange: (f: Partial<ApprovalQueueFilters>) => void;
}

function FilterBar({ filters, onFiltersChange }: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Canal */}
      <input
        type="text"
        placeholder="Canal…"
        value={filters.channel ?? ""}
        onChange={(e) =>
          onFiltersChange({ channel: e.target.value || undefined })
        }
        className="rounded-[4px] border px-2 py-1 text-[12px] w-[120px]"
        style={{ borderColor: MT.border }}
      />

      {/* Esquema */}
      <input
        type="text"
        placeholder="Esquema…"
        value={filters.scheme ?? ""}
        onChange={(e) =>
          onFiltersChange({ scheme: e.target.value || undefined })
        }
        className="rounded-[4px] border px-2 py-1 text-[12px] w-[120px]"
        style={{ borderColor: MT.border }}
      />

      {/* Quick filter: pendientes (siempre pending_review — reset cursor) */}
      <button
        type="button"
        onClick={() => onFiltersChange({ cursor: undefined })}
        className="rounded-[4px] border px-2 py-1 text-[11px] mt-mono hover:brightness-95 transition-[filter]"
        style={{
          background: MT.warningSoft,
          borderColor: MT.warningBorder,
          color: MT.warning,
        }}
      >
        Pendientes
      </button>
    </div>
  );
}

// ---- Main component --------------------------------------------------------

export function ApprovalQueueClient() {
  const { hasPermission } = usePermissions();
  const canWrite = hasPermission("prices:approve");

  const [filters, setFilters] = React.useState<ApprovalQueueFilters>({
    limit: 50,
    include_total: true,
  });
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const [drawerPriceId, setDrawerPriceId] = React.useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useApprovalQueue(filters);

  const items = data?.items ?? [];
  const total = data?.total ?? null;
  const nextCursor = data?.cursor?.next ?? null;

  // ---- Selection helpers ---------------------------------------------------

  const toggleSelect = React.useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = React.useCallback(
    (all: boolean) => {
      if (all) setSelectedIds(new Set(items.map((r) => r.id)));
      else setSelectedIds(new Set());
    },
    [items],
  );

  const clearSelection = React.useCallback(() => setSelectedIds(new Set()), []);

  // ---- Filter update -------------------------------------------------------

  const updateFilters = React.useCallback((patch: Partial<ApprovalQueueFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch, cursor: undefined }));
    clearSelection();
  }, [clearSelection]);

  // ---- Render --------------------------------------------------------------

  if (isError) {
    return (
      <MtError
        message={error instanceof Error ? error.message : "Error al cargar la cola."}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="space-y-4 pb-24">
      {/* Stats */}
      <StatsHeader
        total={total}
        pending={items.length}
        isLoading={isLoading}
      />

      {/* Filtros */}
      <FilterBar filters={filters} onFiltersChange={updateFilters} />

      {/* Tabla */}
      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <MtSkeleton key={i} width="100%" height={42} />
          ))}
        </div>
      ) : items.length === 0 ? (
        <MtEmpty
          title="Sin pendientes — buen trabajo"
          hint="No hay propuestas de precio esperando aprobación. La cola está al día."
        />
      ) : (
        <ApprovalTable
          items={items}
          selectedIds={selectedIds}
          onToggleSelect={toggleSelect}
          onToggleSelectAll={toggleSelectAll}
          onRowClick={(id) => setDrawerPriceId(id)}
        />
      )}

      {/* Paginación cursor */}
      {nextCursor && (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            className="rounded-[5px] border px-4 py-1.5 text-[12px] mt-sans hover:brightness-95 transition-[filter]"
            style={{ borderColor: MT.border, color: MT.ink2 }}
            onClick={() => {
              setFilters((prev) => ({ ...prev, cursor: nextCursor }));
            }}
          >
            Cargar más
          </button>
        </div>
      )}

      {/* Drawer de detalle */}
      <ApprovalDrawer
        priceId={drawerPriceId}
        canWrite={canWrite}
        onClose={() => setDrawerPriceId(null)}
        onActionDone={() => void refetch()}
      />

      {/* Bulk action bar */}
      <BulkActionBar
        selectedIds={[...selectedIds]}
        onClearSelection={clearSelection}
        onBulkActionDone={() => void refetch()}
      />
    </div>
  );
}
