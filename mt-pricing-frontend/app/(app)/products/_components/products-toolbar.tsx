"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Search, X, SlidersHorizontal } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { PRODUCT_FAMILIES } from "@/lib/api/endpoints/products";
import { useDebouncedCallback } from "@/lib/hooks/use-debounced-callback";
import { useProductsListFilters } from "./products-filters";

const ALL = "__all__";

/**
 * Toolbar de filtros del listado `/products`.
 * S2 (US-1A-02-09 frontend): añade Sheet con filtros avanzados (DN, PN, material,
 * data_quality, active, date range) + chips activos + search debounced 300ms.
 */
export function ProductsToolbar() {
  const t = useTranslations("catalog");
  const tFilters = useTranslations("catalog.filters");
  const { filters, setFilter, clear, hasFilters, activeCount } =
    useProductsListFilters();

  // Patrón "controlled with reset key": usamos `key` que cambia con la URL para
  // re-montar el input cuando la URL cambia desde otro origen (back, clear, etc.),
  // evitando setState en efecto (regla react-hooks/set-state-in-effect).
  const debouncedSetSearch = useDebouncedCallback((v: string) => {
    setFilter("q", v || undefined);
  }, 300);

  return (
    <div className="space-y-3">
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
            key={filters.search ?? ""}
            type="search"
            name="q"
            aria-label={t("search")}
            placeholder={t("search")}
            defaultValue={filters.search ?? ""}
            onChange={(e) => debouncedSetSearch(e.target.value)}
            className="pl-8"
            data-testid="products-search"
          />
        </label>

        <Select
          value={filters.family ?? ALL}
          onValueChange={(v) => setFilter("family", v === ALL ? undefined : v)}
        >
          <SelectTrigger
            className="w-full sm:w-44"
            aria-label={tFilters("family")}
            data-testid="products-family-filter"
          >
            <SelectValue placeholder={tFilters("anyFamily")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{tFilters("anyFamily")}</SelectItem>
            {PRODUCT_FAMILIES.map((f) => (
              <SelectItem key={f} value={f} className="capitalize">
                {f}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="text"
          name="brand"
          aria-label="brand"
          placeholder="brand"
          defaultValue={filters.brand ?? ""}
          onChange={(e) => setFilter("brand", e.target.value || undefined)}
          className="w-full sm:w-40"
          data-testid="products-brand-filter"
        />

        <Sheet>
          <SheetTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="products-more-filters"
              aria-label={tFilters("more")}
            >
              <SlidersHorizontal className="h-4 w-4" /> {tFilters("more")}
              {activeCount > 0 ? (
                <Badge className="ml-1" variant="secondary">
                  {activeCount}
                </Badge>
              ) : null}
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-full max-w-md overflow-y-auto">
            <SheetHeader>
              <SheetTitle>{tFilters("title")}</SheetTitle>
              <SheetDescription>{tFilters("advancedHint")}</SheetDescription>
            </SheetHeader>

            <div className="grid gap-4 py-4">
              <FilterField label={tFilters("dn")} htmlFor="filter-dn">
                <Input
                  id="filter-dn"
                  defaultValue={filters.dn ?? ""}
                  onChange={(e) => setFilter("dn", e.target.value || undefined)}
                  data-testid="products-dn-filter"
                />
              </FilterField>
              <FilterField label={tFilters("pn")} htmlFor="filter-pn">
                <Input
                  id="filter-pn"
                  defaultValue={filters.pn ?? ""}
                  onChange={(e) => setFilter("pn", e.target.value || undefined)}
                  data-testid="products-pn-filter"
                />
              </FilterField>
              <FilterField label={tFilters("material")} htmlFor="filter-material">
                <Input
                  id="filter-material"
                  defaultValue={filters.material ?? ""}
                  onChange={(e) =>
                    setFilter("material", e.target.value || undefined)
                  }
                  data-testid="products-material-filter"
                />
              </FilterField>
              <FilterField label={tFilters("dataQuality")}>
                <Select
                  value={filters.data_quality ?? ALL}
                  onValueChange={(v) =>
                    setFilter("data_quality", v === ALL ? undefined : v)
                  }
                >
                  <SelectTrigger
                    aria-label={tFilters("dataQuality")}
                    data-testid="products-quality-filter"
                  >
                    <SelectValue placeholder={tFilters("anyQuality")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL}>{tFilters("anyQuality")}</SelectItem>
                    <SelectItem value="complete">complete</SelectItem>
                    <SelectItem value="partial">partial</SelectItem>
                    <SelectItem value="blocked">blocked</SelectItem>
                  </SelectContent>
                </Select>
              </FilterField>
              <FilterField label={tFilters("status")}>
                <Select
                  value={
                    filters.active === undefined
                      ? ALL
                      : filters.active
                        ? "true"
                        : "false"
                  }
                  onValueChange={(v) =>
                    setFilter("active", v === ALL ? undefined : v)
                  }
                >
                  <SelectTrigger
                    aria-label={tFilters("status")}
                    data-testid="products-status-filter"
                  >
                    <SelectValue placeholder={tFilters("anyStatus")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL}>{tFilters("anyStatus")}</SelectItem>
                    <SelectItem value="true">{tFilters("active")}</SelectItem>
                    <SelectItem value="false">{tFilters("inactive")}</SelectItem>
                  </SelectContent>
                </Select>
              </FilterField>

              <div className="grid grid-cols-2 gap-3">
                <FilterField label={tFilters("createdAfter")} htmlFor="filter-after">
                  <Input
                    id="filter-after"
                    type="date"
                    defaultValue={filters.created_after ?? ""}
                    onChange={(e) =>
                      setFilter("created_after", e.target.value || undefined)
                    }
                    data-testid="products-created-after"
                  />
                </FilterField>
                <FilterField
                  label={tFilters("createdBefore")}
                  htmlFor="filter-before"
                >
                  <Input
                    id="filter-before"
                    type="date"
                    defaultValue={filters.created_before ?? ""}
                    onChange={(e) =>
                      setFilter("created_before", e.target.value || undefined)
                    }
                    data-testid="products-created-before"
                  />
                </FilterField>
              </div>
            </div>

            <SheetFooter>
              {hasFilters ? (
                <Button variant="ghost" size="sm" onClick={clear}>
                  <X className="h-4 w-4" /> {tFilters("clear")}
                </Button>
              ) : null}
              <SheetClose asChild>
                <Button size="sm">{tFilters("apply")}</Button>
              </SheetClose>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        {hasFilters ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={clear}
            data-testid="products-clear-filters"
          >
            <X className="h-4 w-4" /> {tFilters("clear")}
          </Button>
        ) : null}
      </div>

      <ActiveFilterChips />
    </div>
  );
}

function ActiveFilterChips() {
  const { filters, setFilter } = useProductsListFilters();
  const tFilters = useTranslations("catalog.filters");

  const chips: { key: Parameters<typeof setFilter>[0]; label: string }[] = [];
  if (filters.dn) chips.push({ key: "dn", label: `${tFilters("dn")}: ${filters.dn}` });
  if (filters.pn) chips.push({ key: "pn", label: `${tFilters("pn")}: ${filters.pn}` });
  if (filters.material)
    chips.push({ key: "material", label: `${tFilters("material")}: ${filters.material}` });
  if (filters.data_quality)
    chips.push({
      key: "data_quality",
      label: `${tFilters("dataQuality")}: ${filters.data_quality}`,
    });
  if (filters.active !== undefined)
    chips.push({
      key: "active",
      label: filters.active ? tFilters("active") : tFilters("inactive"),
    });
  if (filters.created_after)
    chips.push({
      key: "created_after",
      label: `≥ ${filters.created_after}`,
    });
  if (filters.created_before)
    chips.push({
      key: "created_before",
      label: `≤ ${filters.created_before}`,
    });

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2" data-testid="products-filter-chips">
      {chips.map((c) => (
        <Badge
          key={c.key}
          variant="secondary"
          className="cursor-pointer gap-1"
          onClick={() => setFilter(c.key, undefined)}
        >
          {c.label}
          <X className="h-3 w-3" aria-label={tFilters("remove")} />
        </Badge>
      ))}
    </div>
  );
}

function FilterField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}
