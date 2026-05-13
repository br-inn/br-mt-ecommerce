"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type ERPSyncEvent,
  type ERPSyncStatus,
  listErpEventos,
  retryErpEvento,
} from "@/lib/api/endpoints/erp-sync";

// ---- Badge de estado --------------------------------------------------------

const STATUS_BADGE: Record<
  ERPSyncStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  pending: { label: "Pendiente", variant: "outline" },
  delivered: { label: "Entregado", variant: "default" },
  failed: { label: "Fallido", variant: "destructive" },
  skipped: { label: "Omitido", variant: "secondary" },
};

function StatusBadge({ status }: { status: ERPSyncStatus }) {
  const cfg = STATUS_BADGE[status] ?? { label: status, variant: "outline" as const };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

// ---- Tabla de eventos -------------------------------------------------------

interface EventsTableProps {
  events: ERPSyncEvent[];
  loading: boolean;
  onRetry: (id: string) => Promise<void>;
  retrying: string | null;
}

function EventsTable({ events, loading, onRetry, retrying }: EventsTableProps) {
  if (loading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        Cargando eventos...
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        No hay eventos en este estado.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Tipo</TableHead>
          <TableHead>Entity ID</TableHead>
          <TableHead>Adapter</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead className="text-right">Intentos</TableHead>
          <TableHead>Ref. externa</TableHead>
          <TableHead>Último error</TableHead>
          <TableHead>Entregado</TableHead>
          <TableHead>Creado</TableHead>
          <TableHead />
        </TableRow>
      </TableHeader>
      <TableBody>
        {events.map((ev) => (
          <TableRow key={ev.id}>
            <TableCell className="font-mono text-xs">{ev.event_type}</TableCell>
            <TableCell className="font-mono text-xs">
              {ev.entity_id ? (
                <span title={ev.entity_id}>{ev.entity_id.slice(0, 12)}…</span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>{ev.adapter}</TableCell>
            <TableCell>
              <StatusBadge status={ev.status as ERPSyncStatus} />
            </TableCell>
            <TableCell className="text-right tabular-nums">{ev.attempts}</TableCell>
            <TableCell className="font-mono text-xs">
              {ev.external_ref ? (
                <span title={ev.external_ref}>{ev.external_ref.slice(0, 20)}</span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell
              className="max-w-[180px] truncate text-xs text-destructive"
              title={ev.last_error ?? undefined}
            >
              {ev.last_error ? ev.last_error.slice(0, 60) : <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell className="whitespace-nowrap text-xs">
              {ev.delivered_at
                ? new Date(ev.delivered_at).toLocaleString("es-AE")
                : <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell className="whitespace-nowrap text-xs">
              {ev.created_at
                ? new Date(ev.created_at).toLocaleString("es-AE")
                : <span className="text-muted-foreground">—</span>}
            </TableCell>
            <TableCell>
              {ev.status === "failed" && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={retrying === ev.id}
                  onClick={() => onRetry(ev.id)}
                >
                  {retrying === ev.id ? "Reintentando…" : "Reintentar"}
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---- Tab panel con carga lazy -----------------------------------------------

type TabStatus = ERPSyncStatus;

function TabPanel({
  status,
  active,
  onRetry,
  retrying,
}: {
  status: TabStatus;
  active: boolean;
  onRetry: (id: string) => Promise<void>;
  retrying: string | null;
}) {
  const [events, setEvents] = useState<ERPSyncEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await listErpEventos({ status, limit: 100 });
      setEvents(page.items);
    } catch (err) {
      console.error("listErpEventos error:", err);
    } finally {
      setLoading(false);
      setLoaded(true);
    }
  }, [status]);

  useEffect(() => {
    if (active && !loaded) {
      void load();
    }
  }, [active, loaded, load]);

  const handleRetry = async (id: string) => {
    await onRetry(id);
    // Refresh este tab después del retry
    setLoaded(false);
    await load();
  };

  return (
    <EventsTable
      events={events}
      loading={loading}
      onRetry={handleRetry}
      retrying={retrying}
    />
  );
}

// ---- Componente principal ---------------------------------------------------

const TABS: { value: TabStatus; label: string }[] = [
  { value: "pending", label: "Pendientes" },
  { value: "delivered", label: "Entregados" },
  { value: "failed", label: "Fallidos" },
  { value: "skipped", label: "Omitidos" },
];

export function ErpEventosClient() {
  const [activeTab, setActiveTab] = useState<TabStatus>("pending");
  const [retrying, setRetrying] = useState<string | null>(null);

  const handleRetry = useCallback(async (id: string) => {
    setRetrying(id);
    try {
      await retryErpEvento(id);
    } catch (err) {
      console.error("retryErpEvento error:", err);
    } finally {
      setRetrying(null);
    }
  }, []);

  return (
    <Tabs
      value={activeTab}
      onValueChange={(v) => setActiveTab(v as TabStatus)}
    >
      <TabsList>
        {TABS.map((t) => (
          <TabsTrigger key={t.value} value={t.value}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {TABS.map((t) => (
        <TabsContent key={t.value} value={t.value}>
          <TabPanel
            status={t.value}
            active={activeTab === t.value}
            onRetry={handleRetry}
            retrying={retrying}
          />
        </TabsContent>
      ))}
    </Tabs>
  );
}
