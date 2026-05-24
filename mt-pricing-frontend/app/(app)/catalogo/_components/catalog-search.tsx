"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { useQueryState, parseAsString } from "nuqs";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function useCatalogSearch() {
  const [search, setSearch] = useQueryState(
    "q",
    parseAsString.withDefault("").withOptions({ history: "replace" }),
  );
  return { search, setSearch };
}

const DEBOUNCE_MS = 300;

export function CatalogSearch() {
  const t = useTranslations("catalog");
  const { search, setSearch } = useCatalogSearch();
  const [local, setLocal] = React.useState(search);
  const [prevSearch, setPrevSearch] = React.useState(search);

  // Sync inverso (URL → local) en render cuando la URL cambia desde otro
  // origen (clear filters, navegación). Patrón documentado de React:
  // https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
  if (search !== prevSearch) {
    setPrevSearch(search);
    setLocal(search);
  }

  // Debounce local → URL: el input mantiene su propio estado y propaga a URL
  // tras 300ms cuando difiere.
  React.useEffect(() => {
    if (local === search) return;
    const handle = window.setTimeout(() => {
      void setSearch(local || null);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [local, search, setSearch]);

  return (
    <div className="relative w-full max-w-md">
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        type="search"
        placeholder={t("search")}
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        className="pl-9"
        aria-label={t("search")}
        data-testid="catalog-search"
      />
    </div>
  );
}
