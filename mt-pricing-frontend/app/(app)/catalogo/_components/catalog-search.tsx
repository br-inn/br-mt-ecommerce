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

  // Debounce: el input mantiene su propio estado y propaga a URL tras 300ms.
  React.useEffect(() => {
    const handle = window.setTimeout(() => {
      if (local !== search) void setSearch(local || null);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [local, search, setSearch]);

  // Sync inverso si la URL cambia desde otro origen.
  // TODO(s2): refactor a `useSyncExternalStore` o `key` reset para evitar
  // setState dentro del effect (regla react-hooks/set-state-in-effect).
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
    if (search !== local) setLocal(search);
  }, [search]);

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
