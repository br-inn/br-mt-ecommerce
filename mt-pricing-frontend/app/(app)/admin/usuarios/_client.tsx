"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { Eye } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useRolesCatalog,
  useUsersList,
} from "@/lib/hooks/users-admin/use-users-admin";
import type { UserListItem } from "@/lib/api/endpoints/users-admin";

const ALL = "__all__";
const ACTIVE_ALL = "__all__";
const ACTIVE_TRUE = "true";
const ACTIVE_FALSE = "false";

export function UsersAdminClient() {
  const t = useTranslations("admin.users");
  const tCols = useTranslations("admin.users.columns");
  const tFilters = useTranslations("admin.users.filters");

  const [search, setSearch] = React.useState("");
  const [roleFilter, setRoleFilter] = React.useState<string>(ALL);
  const [activeFilter, setActiveFilter] = React.useState<string>(ACTIVE_ALL);

  const { data: roles } = useRolesCatalog();
  const { data, isLoading, isError } = useUsersList({
    ...(roleFilter !== ALL ? { role: roleFilter } : {}),
    ...(activeFilter !== ACTIVE_ALL
      ? { is_active: activeFilter === ACTIVE_TRUE }
      : {}),
    limit: 200,
  });

  const filtered = React.useMemo<UserListItem[]>(() => {
    if (!data) return [];
    if (!search.trim()) return data;
    const q = search.trim().toLowerCase();
    return data.filter(
      (u) =>
        u.email.toLowerCase().includes(q) ||
        (u.full_name ?? "").toLowerCase().includes(q),
    );
  }, [data, search]);

  return (
    <section className="space-y-4 rounded-md border bg-background p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="grow space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {tFilters("search")}
          </label>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tFilters("searchPlaceholder")}
            className="max-w-sm"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {tFilters("role")}
          </label>
          <Select value={roleFilter} onValueChange={setRoleFilter}>
            <SelectTrigger className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{tFilters("anyRole")}</SelectItem>
              {(roles ?? []).map((r) => (
                <SelectItem key={r.id} value={r.code}>
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">
            {tFilters("active")}
          </label>
          <Select value={activeFilter} onValueChange={setActiveFilter}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ACTIVE_ALL}>{tFilters("any")}</SelectItem>
              <SelectItem value={ACTIVE_TRUE}>{tFilters("yes")}</SelectItem>
              <SelectItem value={ACTIVE_FALSE}>{tFilters("no")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">{t("errors.loadFailed")}</p>
      ) : filtered.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{tCols("email")}</TableHead>
              <TableHead>{tCols("fullName")}</TableHead>
              <TableHead>{tCols("role")}</TableHead>
              <TableHead>{tCols("lastSignIn")}</TableHead>
              <TableHead>{tCols("active")}</TableHead>
              <TableHead className="text-right">{tCols("actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((u) => (
              <TableRow key={u.id}>
                <TableCell className="font-mono text-xs">{u.email}</TableCell>
                <TableCell>{u.full_name ?? "—"}</TableCell>
                <TableCell>
                  {u.role ? (
                    <Badge variant="outline">{u.role.code}</Badge>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {u.last_login_at
                    ? new Date(u.last_login_at).toLocaleString()
                    : "—"}
                </TableCell>
                <TableCell>
                  {u.is_active ? (
                    <Badge>{tCols("yes")}</Badge>
                  ) : (
                    <Badge variant="secondary">{tCols("no")}</Badge>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Button asChild size="sm" variant="ghost">
                    <Link href={`/admin/usuarios/${u.id}`}>
                      <Eye className="h-4 w-4" />
                      {tCols("view")}
                    </Link>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
