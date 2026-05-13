"use client";

import { useState } from "react";
import type React from "react";
import { Globe, Plus, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RbacGuard } from "@/components/auth/rbac-guard";
import { productsApi } from "@/lib/api/endpoints/products";
import type { ProductRelease, ReleaseStatus } from "@/lib/api/endpoints/products";

// ---- Tipos para el Dialog multi-step ----------------------------------
type Step = 1 | 2 | 3;

interface ReleaseFormState {
  market_code: string;
  currency: string;
  local_price: string;
  tax_code: string;
}

const EMPTY_FORM: ReleaseFormState = {
  market_code: "",
  currency: "",
  local_price: "",
  tax_code: "",
};

function AgregarMercadoDialog({
  sku,
  onSuccess,
}: {
  sku: string;
  onSuccess: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>(1);
  const [form, setForm] = useState<ReleaseFormState>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      productsApi.createRelease(sku, {
        market_code: form.market_code.toUpperCase(),
        price_currency: form.currency || null,
        list_price: form.local_price ? Number(form.local_price) : null,
        tax_class: form.tax_code || null,
      }),
    onSuccess: () => {
      setOpen(false);
      setStep(1);
      setForm(EMPTY_FORM);
      setError(null);
      onSuccess();
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : "Error al crear el release.";
      setError(msg);
    },
  });

  const handleOpenChange = (v: boolean) => {
    if (!v) {
      setStep(1);
      setForm(EMPTY_FORM);
      setError(null);
    }
    setOpen(v);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Plus className="h-4 w-4" /> Agregar mercado
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Activar mercado — Paso {step} de 3</DialogTitle>
          <DialogDescription>
            {step === 1 && "Identifica el mercado destino."}
            {step === 2 && "Precio local y datos fiscales."}
            {step === 3 && "Confirma la configuración antes de activar."}
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="grid gap-4 py-4">
            <div className="grid gap-1.5">
              <Label htmlFor="market_code">Código de mercado</Label>
              <Input
                id="market_code"
                placeholder="UAE, KSA, MX, ES…"
                value={form.market_code}
                onChange={(e) =>
                  setForm((f) => ({ ...f, market_code: e.target.value }))
                }
                maxLength={10}
                className="uppercase"
              />
              <p className="text-xs text-muted-foreground">
                Código ISO o código interno de mercado (2-10 caracteres).
              </p>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="grid gap-4 py-4">
            <div className="grid gap-1.5">
              <Label htmlFor="currency">Moneda (ISO 4217)</Label>
              <Input
                id="currency"
                placeholder="AED, SAR, MXN…"
                value={form.currency}
                onChange={(e) =>
                  setForm((f) => ({ ...f, currency: e.target.value.toUpperCase() }))
                }
                maxLength={3}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="local_price">Precio de lista local</Label>
              <Input
                id="local_price"
                type="number"
                min="0"
                step="0.01"
                placeholder="0.00"
                value={form.local_price}
                onChange={(e) =>
                  setForm((f) => ({ ...f, local_price: e.target.value }))
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="tax_code">Clase fiscal</Label>
              <Input
                id="tax_code"
                placeholder="VAT_5_UAE, IVA_16_MX, EXEMPT…"
                value={form.tax_code}
                onChange={(e) =>
                  setForm((f) => ({ ...f, tax_code: e.target.value }))
                }
                maxLength={50}
              />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="grid gap-3 py-4 text-sm">
            <dl className="grid grid-cols-2 gap-2 rounded-lg border bg-muted/30 p-3">
              <dt className="text-muted-foreground">Mercado</dt>
              <dd className="font-medium">{form.market_code.toUpperCase() || "—"}</dd>
              <dt className="text-muted-foreground">Moneda</dt>
              <dd className="font-medium">{form.currency || "—"}</dd>
              <dt className="text-muted-foreground">Precio local</dt>
              <dd className="font-medium">
                {form.local_price
                  ? `${Number(form.local_price).toLocaleString()} ${form.currency}`
                  : "—"}
              </dd>
              <dt className="text-muted-foreground">Clase fiscal</dt>
              <dd className="font-medium font-mono text-xs">{form.tax_code || "—"}</dd>
            </dl>
            {error ? (
              <p className="text-sm text-destructive">{error}</p>
            ) : null}
          </div>
        )}

        <DialogFooter className="gap-2">
          {step > 1 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setStep((s) => (s - 1) as Step)}
              disabled={createMutation.isPending}
            >
              Anterior
            </Button>
          )}
          {step < 3 && (
            <Button
              size="sm"
              onClick={() => {
                if (step === 1 && !form.market_code.trim()) {
                  setError("El código de mercado es obligatorio.");
                  return;
                }
                setError(null);
                setStep((s) => (s + 1) as Step);
              }}
            >
              Siguiente
            </Button>
          )}
          {step === 3 && (
            <Button
              size="sm"
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "Activando…" : "Activar mercado"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// SAP Fiori Semantic Colors para release status
const RELEASE_STATUS_CONFIG: Record<
  ReleaseStatus,
  { label: string; icon: React.ElementType; className: string }
> = {
  draft:        { label: "Borrador",      icon: AlertCircle,  className: "text-muted-foreground" },
  active:       { label: "Activo",        icon: CheckCircle2, className: "text-green-600" },
  suspended:    { label: "Suspendido",    icon: XCircle,      className: "text-yellow-600" },
  discontinued: { label: "Discontinuado", icon: XCircle,      className: "text-red-600" },
};

const MARKET_FLAGS: Record<string, string> = {
  UAE: "🇦🇪",
  KSA: "🇸🇦",
  MX:  "🇲🇽",
  ES:  "🇪🇸",
  US:  "🇺🇸",
  EU:  "🇪🇺",
};

function ReleaseStatusIcon({ status }: { status: ReleaseStatus }) {
  const cfg = RELEASE_STATUS_CONFIG[status] ?? RELEASE_STATUS_CONFIG.draft;
  const Icon = cfg.icon;
  return (
    <span className={`flex items-center gap-1 text-sm font-medium ${cfg.className}`}>
      <Icon className="h-4 w-4" />
      {cfg.label}
    </span>
  );
}

interface Props {
  sku: string;
}

export function MercadosClient({ sku }: Props) {
  const queryClient = useQueryClient();
  const [activating, setActivating] = useState<string | null>(null);

  const { data: releases, isLoading, isError } = useQuery({
    queryKey: ["product-releases", sku],
    queryFn: () => productsApi.listReleases(sku),
  });

  const activateMutation = useMutation({
    mutationFn: (marketCode: string) => productsApi.activateRelease(sku, marketCode),
    onMutate: (mc) => setActivating(mc),
    onSettled: () => {
      setActivating(null);
      void queryClient.invalidateQueries({ queryKey: ["product-releases", sku] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: (marketCode: string) => productsApi.deactivateRelease(sku, marketCode),
    onMutate: (mc) => setActivating(mc),
    onSettled: () => {
      setActivating(null);
      void queryClient.invalidateQueries({ queryKey: ["product-releases", sku] });
    },
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6 text-sm text-destructive">
          Error cargando releases.
        </CardContent>
      </Card>
    );
  }

  const activeCount = releases?.filter((r) => r.is_active).length ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-muted-foreground" />
            Releases por Mercado
          </CardTitle>
          <CardDescription>
            Configuración del producto por entidad legal / mercado.{" "}
            <span className="font-medium text-foreground">
              {activeCount} mercado{activeCount !== 1 ? "s" : ""} activo{activeCount !== 1 ? "s" : ""}
            </span>
          </CardDescription>
        </div>
        <RbacGuard permissions={["products:write"]}>
          <AgregarMercadoDialog
            sku={sku}
            onSuccess={() =>
              void queryClient.invalidateQueries({
                queryKey: ["product-releases", sku],
              })
            }
          />
        </RbacGuard>
      </CardHeader>

      <CardContent>
        {!releases || releases.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <Globe className="h-8 w-8 opacity-30" />
            <p className="text-sm">
              Este producto aún no tiene releases configurados para ningún mercado.
            </p>
            <p className="text-xs">
              Los releases controlan precio local, impuesto y activación por país.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mercado</TableHead>
                <TableHead>Nombre local</TableHead>
                <TableHead>SKU local</TableHead>
                <TableHead className="text-right">Precio</TableHead>
                <TableHead>Clase fiscal</TableHead>
                <TableHead>Estado</TableHead>
                <RbacGuard permissions={["products:write"]}>
                  <TableHead className="text-right">Acciones</TableHead>
                </RbacGuard>
              </TableRow>
            </TableHeader>
            <TableBody>
              {releases.map((release: ProductRelease) => {
                const flag = MARKET_FLAGS[release.market_code] ?? "🌐";
                const isProcessing = activating === release.market_code;
                return (
                  <TableRow key={release.id}>
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-1.5">
                        <span>{flag}</span>
                        <span>{release.market_code}</span>
                      </span>
                    </TableCell>
                    <TableCell className="text-sm">
                      {release.local_name ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {release.local_sku ?? (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right text-sm">
                      {release.list_price != null ? (
                        <span>
                          {release.list_price.toLocaleString()}{" "}
                          <span className="text-muted-foreground">
                            {release.price_currency ?? ""}
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {release.tax_class ? (
                        <Badge variant="outline" className="font-mono text-xs">
                          {release.tax_class}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <ReleaseStatusIcon status={release.status} />
                    </TableCell>
                    <RbacGuard permissions={["products:write"]}>
                      <TableCell className="text-right">
                        {release.is_active ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => deactivateMutation.mutate(release.market_code)}
                          >
                            Suspender
                          </Button>
                        ) : (
                          <Button
                            variant="default"
                            size="sm"
                            disabled={isProcessing}
                            onClick={() => activateMutation.mutate(release.market_code)}
                          >
                            Activar
                          </Button>
                        )}
                      </TableCell>
                    </RbacGuard>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
