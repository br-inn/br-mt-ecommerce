"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { RbacGuard } from "@/components/auth/rbac-guard";
import { FxRateForm } from "@/components/admin/fx-rate-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useCurrenciesAdmin } from "@/lib/hooks/currencies/use-currencies";
import { useFxRatesAdmin } from "@/lib/hooks/fx/use-fx-mutations";

const ALL = "__all__";

/**
 * Client del page `/admin/fx-rates` — DataTable + filtros (from/to/active) +
 * dialog modal "Nueva tasa" via `<FxRateForm>`.
 *
 * - Render `vigente badge` cuando `effective_to === null`.
 * - Filtros from/to alimentan el query param hacia el endpoint
 *   `/api/v1/fx-rates`.
 * - Toggle `only_active` para ver sólo el rate vigente por par.
 */
export function FxRatesAdminClient() {
  const t = useTranslations("fx_rates");
  const tCols = useTranslations("fx_rates.columns");
  const tFilters = useTranslations("fx_rates.filters");

  const [from, setFrom] = React.useState<string>(ALL);
  const [to, setTo] = React.useState<string>(ALL);
  const [onlyActive, setOnlyActive] = React.useState(false);

  const { data: currencies } = useCurrenciesAdmin();
  const codes = (currencies ?? []).filter((c) => c.active).map((c) => c.code);

  const filters = React.useMemo(
    () => ({
      from_currency: from === ALL ? undefined : from,
      to_currency: to === ALL ? undefined : to,
      only_active: onlyActive || undefined,
    }),
    [from, to, onlyActive],
  );

  const { data, isLoading, isError } = useFxRatesAdmin(filters);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 justify-between">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label className="text-xs uppercase">{tFilters("from")}</Label>
            <Select value={from} onValueChange={setFrom}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder={tFilters("any")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("any")}</SelectItem>
                {codes.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs uppercase">{tFilters("to")}</Label>
            <Select value={to} onValueChange={setTo}>
              <SelectTrigger className="w-32">
                <SelectValue placeholder={tFilters("any")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>{tFilters("any")}</SelectItem>
                {codes.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="button"
            size="sm"
            variant={onlyActive ? "default" : "outline"}
            onClick={() => setOnlyActive((v) => !v)}
          >
            {onlyActive ? tFilters("activeOnly") : tFilters("showAll")}
          </Button>
          {(from !== ALL || to !== ALL || onlyActive) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setFrom(ALL);
                setTo(ALL);
                setOnlyActive(false);
              }}
            >
              {tFilters("clear")}
            </Button>
          )}
        </div>
        <RbacGuard permissions={["fx:manage"]}>
          <FxRateForm availableCodes={codes} />
        </RbacGuard>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
      ) : !data || data.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("empty.rates")}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{tCols("from_currency")}</TableHead>
              <TableHead>{tCols("to_currency")}</TableHead>
              <TableHead>{tCols("rate")}</TableHead>
              <TableHead>{tCols("effective_from")}</TableHead>
              <TableHead>{tCols("effective_to")}</TableHead>
              <TableHead>{tCols("source")}</TableHead>
              <TableHead>{tCols("status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((r) => (
              <TableRow
                key={r.id}
                className={r.effective_to === null ? "bg-primary/5" : undefined}
              >
                <TableCell className="font-mono">{r.from_currency}</TableCell>
                <TableCell className="font-mono">{r.to_currency}</TableCell>
                <TableCell className="font-mono">
                  {Number(r.rate).toFixed(6)}
                </TableCell>
                <TableCell className="text-xs">
                  {new Date(r.effective_from).toLocaleString()}
                </TableCell>
                <TableCell className="text-xs">
                  {r.effective_to
                    ? new Date(r.effective_to).toLocaleString()
                    : "—"}
                </TableCell>
                <TableCell>{r.source ?? "—"}</TableCell>
                <TableCell>
                  {r.effective_to === null ? (
                    <Badge>{t("statuses.current")}</Badge>
                  ) : (
                    <Badge variant="outline">{t("statuses.expired")}</Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
