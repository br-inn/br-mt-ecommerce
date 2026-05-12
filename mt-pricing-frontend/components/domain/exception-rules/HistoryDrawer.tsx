"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useExceptionRulesHistory } from "@/lib/hooks/exception-rules/use-exception-rules";

/**
 * Drawer lateral con el historial completo de exception rules
 * (activas + cerradas), ordenado por created_at desc.
 */
export function HistoryDrawer() {
  const [open, setOpen] = React.useState(false);
  const { data, isLoading, isError } = useExceptionRulesHistory(100);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          Ver historial
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full max-w-3xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Historial de exception rules</SheetTitle>
          <SheetDescription>
            Todas las versiones de reglas — activas y cerradas — ordenadas por
            fecha de creación descendente.
          </SheetDescription>
        </SheetHeader>
        <div className="mt-4">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-md" />
              ))}
            </div>
          ) : isError ? (
            <p className="text-sm text-destructive">
              Error al cargar el historial.
            </p>
          ) : !data || data.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Sin historial registrado.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Código</TableHead>
                  <TableHead>v</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Vigente desde</TableHead>
                  <TableHead>Vigente hasta</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.code}</TableCell>
                    <TableCell className="text-center text-xs">
                      {r.version}
                    </TableCell>
                    <TableCell>
                      {r.active ? (
                        <Badge variant="default">Activa</Badge>
                      ) : (
                        <Badge variant="outline">Cerrada</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs">
                      {r.effective_from
                        ? new Date(r.effective_from).toLocaleString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {r.effective_to
                        ? new Date(r.effective_to).toLocaleString()
                        : r.active
                          ? "Vigente"
                          : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
