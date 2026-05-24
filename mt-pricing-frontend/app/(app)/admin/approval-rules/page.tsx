"use client";

import * as React from "react";
import { Plus, Pencil } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  procurementApi,
  type ApprovalRuleRead,
  type ApprovalRuleCreatePayload,
} from "@/lib/api/endpoints/procurement";

function RuleForm({
  open,
  onOpenChange,
  initial,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial: Partial<ApprovalRuleRead> | null;
  onSaved: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = React.useState<ApprovalRuleCreatePayload>({
    min_amount: "0",
    max_amount: null,
    approver_role: null,
    timeout_hours: 48,
    priority: 0,
    is_active: true,
  });

  React.useEffect(() => {
    if (initial) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setForm({
        min_amount: initial.min_amount ?? "0",
        max_amount: initial.max_amount ?? null,
        approver_role: initial.approver_role ?? null,
        timeout_hours: initial.timeout_hours ?? 48,
        priority: initial.priority ?? 0,
        is_active: initial.is_active ?? true,
      });
    }
  }, [initial]);

  function patch(field: string, value: unknown) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const { mutate: save, isPending } = useMutation({
    mutationFn: () => {
      if (initial?.id) {
        return procurementApi.updateApprovalRule(initial.id, form);
      }
      return procurementApi.createApprovalRule(form);
    },
    onSuccess: () => {
      toast.success(initial?.id ? "Regla actualizada" : "Regla creada");
      queryClient.invalidateQueries({ queryKey: ["approval-rules"] });
      onSaved();
      onOpenChange(false);
    },
    onError: () => toast.error("Error al guardar la regla"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full max-w-md flex-col overflow-y-auto">
        <SheetHeader>
          <SheetTitle>
            {initial?.id ? "Editar regla" : "Nueva regla de aprobación"}
          </SheetTitle>
        </SheetHeader>
        <div className="flex flex-1 flex-col gap-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Importe mínimo (AED)</Label>
              <Input
                type="number"
                min="0"
                step="any"
                value={form.min_amount ?? ""}
                onChange={(e) => patch("min_amount", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Importe máximo (AED)</Label>
              <Input
                type="number"
                min="0"
                step="any"
                value={form.max_amount ?? ""}
                placeholder="Sin límite"
                onChange={(e) =>
                  patch("max_amount", e.target.value || null)
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Rol aprobador</Label>
              <Input
                value={form.approver_role ?? ""}
                onChange={(e) =>
                  patch("approver_role", e.target.value || null)
                }
                placeholder="gerente / ti"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Timeout (horas)</Label>
              <Input
                type="number"
                min="0"
                value={form.timeout_hours ?? 48}
                onChange={(e) =>
                  patch("timeout_hours", parseInt(e.target.value, 10) || 0)
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label>Prioridad</Label>
              <Input
                type="number"
                min="0"
                value={form.priority ?? 0}
                onChange={(e) =>
                  patch("priority", parseInt(e.target.value, 10) || 0)
                }
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Timeout = 0 aplica auto-aprobación. Mayor prioridad (número menor) = se evalúa primero.
          </p>
        </div>
        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
            Cancelar
          </Button>
          <Button onClick={() => save()} disabled={isPending}>
            {isPending ? "Guardando..." : "Guardar"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export default function ApprovalRulesPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["approval-rules"],
    queryFn: () => procurementApi.listApprovalRules(),
  });

  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<ApprovalRuleRead | null>(null);

  function openNew() {
    setEditing(null);
    setSheetOpen(true);
  }

  function openEdit(rule: ApprovalRuleRead) {
    setEditing(rule);
    setSheetOpen(true);
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Matriz de aprobaciones
          </h1>
          <p className="text-sm text-muted-foreground">
            Reglas de enrutamiento por importe y rol
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="mr-2 size-4" />
          Nueva regla
        </Button>
      </header>

      <Card>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Prioridad</TableHead>
                <TableHead>Mínimo AED</TableHead>
                <TableHead>Máximo AED</TableHead>
                <TableHead>Rol aprobador</TableHead>
                <TableHead>Timeout (h)</TableHead>
                <TableHead>Activa</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Skeleton className="h-8 w-full" />
                  </TableCell>
                </TableRow>
              )}
              {isError && (
                <TableRow>
                  <TableCell colSpan={7} className="text-destructive">
                    Error al cargar las reglas
                  </TableCell>
                </TableRow>
              )}
              {(data ?? []).map((rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="text-xs font-mono">{rule.priority}</TableCell>
                  <TableCell className="text-xs">{rule.min_amount}</TableCell>
                  <TableCell className="text-xs">{rule.max_amount ?? "∞"}</TableCell>
                  <TableCell className="text-xs">
                    {rule.approver_role ?? (
                      <span className="text-muted-foreground italic">auto</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs">
                    {rule.timeout_hours === 0 ? (
                      <span className="text-muted-foreground italic">auto</span>
                    ) : (
                      rule.timeout_hours
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant={rule.is_active ? "success" : "secondary"}>
                      {rule.is_active ? "Sí" : "No"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => openEdit(rule)}
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <RuleForm
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        initial={editing}
        onSaved={() => refetch()}
      />
    </div>
  );
}
