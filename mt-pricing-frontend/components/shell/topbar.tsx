"use client";

import Link from "next/link";
import { Bell, LogOut, Search, User as UserIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { useUIStore } from "@/lib/stores/ui-store";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/components/auth/auth-provider";
import { LocaleSwitcher } from "@/components/shell/locale-switcher";
import { MT } from "@/components/mt/tokens";

const NOTIF_COUNT = 3;

function initials(name: string | null, email: string): string {
  if (name) {
    const parts = name.trim().split(/\s+/);
    return (parts[0]?.[0] ?? "").concat(parts[1]?.[0] ?? "").toUpperCase() || "?";
  }
  return email.slice(0, 2).toUpperCase();
}

export function Topbar() {
  const t = useTranslations("shell");
  const tCmd = useTranslations("command");
  const setCommandPaletteOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const { user, signOut } = useAuth();

  return (
    <header
      className="flex h-12 shrink-0 items-center gap-4 px-4"
      style={{
        background: MT.surface,
        borderBottom: `1px solid ${MT.border}`,
        boxShadow: `inset 0 -1px 0 ${MT.border}, inset 0 2px 0 ${MT.brand}`,
      }}
    >
      <div className="flex flex-1 justify-center">
        <button
          type="button"
          aria-label={t("openCommand")}
          onClick={() => setCommandPaletteOpen(true)}
          className="flex h-[30px] w-full max-w-[460px] cursor-pointer items-center gap-2 rounded-md border px-2.5 text-[12.5px] transition-colors duration-150 hover:bg-mt-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1"
          style={{
            background: MT.surface3,
            borderColor: MT.border,
            color: MT.ink3,
          }}
        >
          <Search className="size-[13px]" />
          <span className="flex-1 truncate text-left">{tCmd("placeholder")}</span>
          <span
            className="mt-mono inline-flex items-center rounded-[4px] border px-1.5 py-px text-[10.5px]"
            style={{ background: MT.surface, borderColor: MT.border }}
          >
            ⌘K
          </span>
        </button>
      </div>

      <div className="flex items-center gap-3" style={{ color: MT.ink2 }}>
        <button
          type="button"
          aria-label="Notificaciones"
          className="relative grid size-7 cursor-pointer place-items-center rounded-md transition-colors duration-150 hover:bg-mt-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1"
        >
          <Bell className="size-[15px]" />
          {NOTIF_COUNT > 0 ? (
            <span
              className="absolute right-1 top-1 grid h-3.5 min-w-[14px] place-items-center rounded-full px-[3px] text-[9px] font-semibold text-white"
              style={{
                background: MT.brand,
                border: `1.5px solid ${MT.surface}`,
              }}
            >
              {NOTIF_COUNT}
            </span>
          ) : null}
        </button>

        <LocaleSwitcher />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={t("userMenu")}
              data-testid="user-menu-trigger"
              className="grid size-[26px] shrink-0 place-items-center rounded-full text-[10.5px] font-semibold text-white"
              style={{
                background: `linear-gradient(135deg, ${MT.brand}, ${MT.brandLight})`,
              }}
            >
              <Avatar className="size-[26px]">
                {user?.avatarUrl ? (
                  <AvatarImage src={user.avatarUrl} alt={user.fullName ?? user.email} />
                ) : null}
                <AvatarFallback className="bg-transparent text-[10.5px] font-semibold text-white">
                  {user ? initials(user.fullName, user.email) : "PS"}
                </AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            {user ? (
              <>
                <DropdownMenuLabel className="flex flex-col">
                  <span className="font-medium">{user.fullName ?? user.email}</span>
                  <span className="text-xs text-muted-foreground">{user.email}</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/account" className="flex w-full items-center">
                    <UserIcon className="mr-2 h-4 w-4" />
                    {t("myAccount")}
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  data-testid="user-menu-signout"
                  onSelect={(e) => {
                    e.preventDefault();
                    void signOut();
                  }}
                  className="text-destructive focus:text-destructive"
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  {t("signOut")}
                </DropdownMenuItem>
              </>
            ) : (
              <DropdownMenuItem asChild>
                <Link href="/login">{t("userMenu")}</Link>
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
