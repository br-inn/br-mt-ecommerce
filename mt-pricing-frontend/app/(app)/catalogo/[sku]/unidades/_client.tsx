"use client";

import { Ruler, ArrowRight, Plus, Trash2 } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
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
import { useProduct } from "@/lib/hooks/products/use-product";
import type { ProductUomConversion } from "@/lib/api/endpoints/products";

interface Props {
  sku: string;
}

export function UnidadesClient({ sku }: Props) {
  const queryClient = useQueryClient();
  const { data: product, isLoading: loadingProduct } = useProduct(sku);

  const { data: conversions, isLoading: loadingConv } = useQuery({
    queryKey: ["product-uom-conversions", sku],
    queryFn: () => productsApi.listUomConversions(sku),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ uomFrom, uomTo }: { uomFrom: string; uomTo: string }) =>
      productsApi.deleteUomConversion(sku, uomFrom, uomTo),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ["product-uom-conversions", sku] });
    },
  });

  const isLoading = loadingProduct || loadingConv;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-28 w-full rounded-lg" />
        <Skeleton className="h-48 w-full rounded-lg" />
      </div>
    );
  }

  const baseUom = (product as { base_uom?: string | null } | undefined)?.base_uom ?? "UNIT";

  return (
    <div className="flex flex-col gap-4">
      {/* Card de UoM base — inspirado en SAP MM base unit of measure */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Ruler className="h-5 w-5 text-muted-foreground" />
            Unidad de Medida Base
          </CardTitle>
          <CardDescription>
            Todas las transacciones (stock, compras, ventas) se calculan en esta UoM.
            Las conversiones definen factores para empaques o unidades alternativas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Badge variant="default" className="px-4 py-1.5 text-base font-bold">
              {baseUom}
            </Badge>
            <span className="text-sm text-muted-foreground">UoM canónica del producto</span>
          </div>
        </CardContent>
      </Card>

      {/* Tabla de conversiones — SAP MM alternate UoM */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>Conversiones de Unidades</CardTitle>
            <CardDescription>
              Equivalencias entre unidades alternativas y la UoM base.
              Ej: 1 BOX = 12 {baseUom}.
            </CardDescription>
          </div>
          <RbacGuard permissions={["products:write"]}>
            <Button variant="outline" size="sm" disabled>
              <Plus className="h-4 w-4" /> Agregar
            </Button>
          </RbacGuard>
        </CardHeader>

        <CardContent>
          {!conversions || conversions.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
              <Ruler className="h-8 w-8 opacity-30" />
              <p className="text-sm">No hay conversiones definidas para este producto.</p>
              <p className="text-xs">
                Las conversiones permiten comprar en BOX y registrar stock en {baseUom}.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>De</TableHead>
                  <TableHead></TableHead>
                  <TableHead>A</TableHead>
                  <TableHead className="text-right">Factor</TableHead>
                  <TableHead>Dirección</TableHead>
                  <TableHead>Estado</TableHead>
                  <RbacGuard permissions={["products:write"]}>
                    <TableHead className="text-right">Acciones</TableHead>
                  </RbacGuard>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversions.map((conv: ProductUomConversion) => (
                  <TableRow key={conv.id}>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">
                        {conv.uom_from}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono">
                        {conv.uom_to}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono font-semibold">
                      × {conv.factor}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {conv.direction ?? "—"}
                    </TableCell>
                    <TableCell>
                      {conv.is_active ? (
                        <span className="text-sm text-green-600 font-medium">Activa</span>
                      ) : (
                        <span className="text-sm text-muted-foreground">Inactiva</span>
                      )}
                    </TableCell>
                    <RbacGuard permissions={["products:write"]}>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() =>
                            deleteMutation.mutate({
                              uomFrom: conv.uom_from,
                              uomTo: conv.uom_to,
                            })
                          }
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </RbacGuard>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
