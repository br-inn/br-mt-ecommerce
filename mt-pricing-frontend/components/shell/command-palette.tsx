"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import {
  Home,
  Package,
  Plus,
  Search,
  Upload,
  User as UserIcon,
} from "lucide-react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useUIStore } from "@/lib/stores/ui-store";
import { usePermissions } from "@/lib/hooks/use-permissions";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import {
  productsApi,
  type ProductSearchHit,
} from "@/lib/api/endpoints/products";
import {
  usersApi,
  type UserListItem,
} from "@/lib/api/endpoints/users";

/**
 * Cmd-K palette (Sprint 1.5).
 *
 * - Atajo Cmd+K / Ctrl+K para abrir.
 * - Acciones rápidas siempre visibles (filtradas por permisos).
 * - Búsqueda de SKUs (>=2 chars) vía TanStack Query con `staleTime: 30s`.
 * - Búsqueda de usuarios visible sólo con `users:read`.
 */
const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

export function CommandPalette() {
  const t = useTranslations("command");
  const open = useUIStore((s) => s.commandPaletteOpen);
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const router = useRouter();
  const { hasPermission } = usePermissions();

  const canReadUsers = hasPermission("users:read");
  const canCreateSku = hasPermission("products:write");
  const canImport = hasPermission("imports:write") || hasPermission("imports:read");

  const [query, setQuery] = React.useState("");
  const debouncedQuery = useDebouncedValue(query.trim(), DEBOUNCE_MS);
  const queryReady = debouncedQuery.length >= MIN_QUERY_LENGTH;

  // Atajo Cmd/Ctrl-K.
  React.useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen(!open);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, setOpen]);

  // Reset query al cerrar.
  React.useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const skuResults = useQuery<ProductSearchHit[], Error>({
    queryKey: ["search", "products", debouncedQuery],
    queryFn: () => productsApi.search(debouncedQuery, 8),
    enabled: open && queryReady,
    staleTime: 30_000,
  });

  const userResults = useQuery<UserListItem[], Error>({
    queryKey: ["search", "users", debouncedQuery],
    queryFn: () =>
      // Backend list: limit + filtra client-side por email/nombre. Suficiente
      // para palette; un endpoint dedicado ?q=… llega Sprint 2.
      usersApi.list({ limit: 50 }).then((items) =>
        items
          .filter((u) => {
            const haystack = `${u.email} ${u.full_name ?? ""}`.toLowerCase();
            return haystack.includes(debouncedQuery.toLowerCase());
          })
          .slice(0, 5),
      ),
    enabled: open && queryReady && canReadUsers,
    staleTime: 30_000,
  });

  const navigate = (href: string) => {
    setOpen(false);
    setQuery("");
    router.push(href);
  };

  const isSearching =
    queryReady &&
    (skuResults.isFetching || (canReadUsers && userResults.isFetching));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="overflow-hidden p-0">
        <DialogTitle className="sr-only">{t("placeholder")}</DialogTitle>
        <Command className="rounded-lg" shouldFilter={false}>
          <Command.Input
            value={query}
            onValueChange={setQuery}
            className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none placeholder:text-muted-foreground"
            placeholder={t("placeholder")}
          />
          <Command.List className="max-h-96 overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
              {isSearching ? t("loading") : t("noResults")}
            </Command.Empty>

            <Command.Group heading={t("actions")}>
              <Command.Item
                onSelect={() => navigate("/dashboard")}
                value="goto-dashboard"
                className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
              >
                <Home className="h-4 w-4" /> {t("goDashboard")}
              </Command.Item>
              <Command.Item
                onSelect={() => navigate("/catalogo")}
                value="goto-catalog"
                className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
              >
                <Package className="h-4 w-4" /> {t("goCatalog")}
              </Command.Item>
              {canCreateSku ? (
                <Command.Item
                  onSelect={() => navigate("/catalogo/nuevo")}
                  value="new-sku"
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
                >
                  <Plus className="h-4 w-4" /> {t("newSku")}
                </Command.Item>
              ) : null}
              {canImport ? (
                <Command.Item
                  onSelect={() => navigate("/admin/imports")}
                  value="goto-imports"
                  className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
                >
                  <Upload className="h-4 w-4" /> {t("goImports")}
                </Command.Item>
              ) : null}
            </Command.Group>

            {queryReady && skuResults.data && skuResults.data.length > 0 ? (
              <Command.Group heading={t("products")}>
                {skuResults.data.map((hit) => (
                  <Command.Item
                    key={hit.id}
                    value={`product-${hit.id}`}
                    onSelect={() => navigate(`/catalogo/${hit.sku}`)}
                    className="flex cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    <span className="flex items-center gap-2">
                      <Search className="h-3 w-3 text-muted-foreground" />
                      <span className="font-mono text-xs font-semibold">
                        {hit.sku}
                      </span>
                      <span className="text-muted-foreground">
                        {hit.display_name ?? "(sin nombre)"}
                      </span>
                    </span>
                    {hit.family ? (
                      <span className="text-xs text-muted-foreground capitalize">
                        {hit.family}
                      </span>
                    ) : null}
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}

            {canReadUsers &&
            queryReady &&
            userResults.data &&
            userResults.data.length > 0 ? (
              <Command.Group heading={t("users")}>
                {userResults.data.map((u) => (
                  <Command.Item
                    key={u.id}
                    value={`user-${u.id}`}
                    onSelect={() => navigate(`/admin/usuarios/${u.id}`)}
                    className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-2 text-sm aria-selected:bg-accent"
                  >
                    <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs">{u.email}</span>
                    {u.full_name ? (
                      <span className="text-xs text-muted-foreground">
                        · {u.full_name}
                      </span>
                    ) : null}
                  </Command.Item>
                ))}
              </Command.Group>
            ) : null}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
