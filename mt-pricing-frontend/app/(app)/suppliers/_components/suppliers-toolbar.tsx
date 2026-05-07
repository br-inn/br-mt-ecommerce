"use client";

import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SUPPLIER_CURRENCIES } from "@/lib/api/endpoints/suppliers";
import { useSuppliersListFilters } from "./suppliers-filters";

const ALL = "__all__";

/**
 * Toolbar de filtros del listado `/suppliers` (legacy).
 * Filtros: search por nombre/código, currency contractual, active toggle.
 */
export function SuppliersToolbar() {
  const t = useTranslations("suppliers");
  const tFilters = useTranslations("suppliers.filters");
  const { filters, setFilter, clear, hasFilters } = useSuppliersListFilters();

  return (
    <div
      className="flex flex-col gap-3 sm:flex-row sm:items-center sm:flex-wrap"
      role="search"
      aria-label={t("search")}
    >
      <label className="relative w-full sm:max-w-sm">
        <Search
          className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          type="search"
          name="q"
          aria-label={t("search")}
          placeholder={t("search")}
          defaultValue={filters.search ?? ""}
          onChange={(e) => setFilter("q", e.target.value || undefined)}
          className="pl-8"
          data-testid="suppliers-search"
        />
      </label>

      <Select
        value={filters.contract_currency ?? ALL}
        onValueChange={(v) =>
          setFilter("contract_currency", v === ALL ? undefined : v)
        }
      >
        <SelectTrigger
          className="w-full sm:w-44"
          aria-label={tFilters("currency")}
          data-testid="suppliers-currency-filter"
        >
          <SelectValue placeholder={tFilters("anyCurrency")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{tFilters("anyCurrency")}</SelectItem>
          {SUPPLIER_CURRENCIES.map((c) => (
            <SelectItem key={c} value={c}>
              {c}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={
          filters.active === undefined
            ? ALL
            : filters.active
              ? "true"
              : "false"
        }
        onValueChange={(v) => setFilter("active", v === ALL ? undefined : v)}
      >
        <SelectTrigger
          className="w-full sm:w-36"
          aria-label={tFilters("status")}
          data-testid="suppliers-active-filter"
        >
          <SelectValue placeholder={tFilters("anyStatus")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>{tFilters("anyStatus")}</SelectItem>
          <SelectItem value="true">{tFilters("active")}</SelectItem>
          <SelectItem value="false">{tFilters("inactive")}</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={clear}
          data-testid="suppliers-clear-filters"
        >
          <X className="h-4 w-4" /> {tFilters("clear")}
        </Button>
      ) : null}
    </div>
  );
}
