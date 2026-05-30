"use client";

import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { COST_SCHEMES } from "@/lib/api/endpoints/costs";
import { useSchemes } from "@/lib/hooks/costs/use-schemes";
import { useSuppliers } from "@/lib/hooks/suppliers/use-suppliers";
import { useCostosListFilters } from "./costos-filters";

const ALL = "__all__";

/**
 * Toolbar del listado global de costes (tab "Costes").
 *
 * Controles: búsqueda por SKU, esquema (`useSchemes` con fallback a
 * `COST_SCHEMES`), proveedor (`useSuppliers`), fecha de vigencia (`valid_on`)
 * y toggle de histórico (`include_history`). Todo en URL vía
 * `useCostosListFilters`.
 */
export function CostosToolbar() {
  const t = useTranslations("costos");
  const tFilters = useTranslations("costos.filters");
  const { filters, setFilter, clear, hasFilters } = useCostosListFilters();

  const { data: schemes } = useSchemes();
  const schemeCodes =
    schemes && schemes.length > 0 ? schemes.map((s) => s.code) : [...COST_SCHEMES];

  const { data: suppliersData } = useSuppliers({ active: true });
  const suppliers = suppliersData?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div
      className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center"
      role="search"
      aria-label={t("search")}
    >
      <label className="relative w-full sm:max-w-xs">
        <Search
          className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          name="q"
          aria-label={t("search")}
          placeholder={t("search")}
          defaultValue={filters.sku ?? ""}
          onChange={(e) => setFilter("q", e.target.value || undefined)}
          className="pl-8"
          data-testid="costos-search"
        />
      </label>

      <Select
        value={filters.scheme ?? ALL}
        onValueChange={(v) => setFilter("scheme", v === ALL ? undefined : v)}
      >
        <SelectTrigger
          className="w-full sm:w-48"
          aria-label={t("columns.scheme")}
          data-testid="costos-scheme-filter"
        >
          <SelectValue placeholder={tFilters("anyScheme")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{tFilters("anyScheme")}</SelectItem>
          {schemeCodes.map((code) => (
            <SelectItem key={code} value={code}>
              {code}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.supplier ?? ALL}
        onValueChange={(v) => setFilter("supplier", v === ALL ? undefined : v)}
      >
        <SelectTrigger
          className="w-full sm:w-52"
          aria-label={t("columns.supplier")}
          data-testid="costos-supplier-filter"
        >
          <SelectValue placeholder={tFilters("anySupplier")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{tFilters("anySupplier")}</SelectItem>
          {suppliers.map((s) => (
            <SelectItem key={s.code} value={s.code}>
              {s.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <label className="flex flex-col gap-1 text-xs text-muted-foreground">
        <span className="sr-only">{tFilters("validOn")}</span>
        <Input
          type="date"
          aria-label={tFilters("validOn")}
          value={filters.valid_on ?? ""}
          onChange={(e) => setFilter("valid_on", e.target.value || undefined)}
          className="w-full sm:w-44"
          data-testid="costos-valid-on"
        />
      </label>

      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={filters.include_history ?? false}
          onCheckedChange={(checked) =>
            setFilter("include_history", checked ? "true" : undefined)
          }
          aria-label={tFilters("showHistory")}
          data-testid="costos-history-toggle"
        />
        {tFilters("showHistory")}
      </label>

      {hasFilters ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={clear}
          data-testid="costos-clear-filters"
        >
          <X className="h-4 w-4" /> {tFilters("clear")}
        </Button>
      ) : null}
    </div>
  );
}

export default CostosToolbar;
