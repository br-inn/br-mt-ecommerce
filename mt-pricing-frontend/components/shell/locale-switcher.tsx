"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Languages, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { setLocale } from "@/app/actions/locale";
import { isLocale, locales, type Locale } from "@/lib/i18n/config";

const LABELS: Record<Locale, { label: string; flag: string }> = {
  es: { label: "Español", flag: "ES" },
  en: { label: "English", flag: "EN" },
};

/**
 * Selector de idioma de la UI. Llama a `setLocale` (Server Action) que persiste
 * la cookie `mt-locale` y revalida el layout. Tras la mutación llamamos a
 * `router.refresh()` para que `next-intl` recargue messages en el cliente.
 */
export function LocaleSwitcher() {
  const t = useTranslations("shell");
  const current = useLocale();
  const currentLocale: Locale = isLocale(current) ? current : "es";
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const onPick = (next: Locale) => {
    if (next === currentLocale) return;
    startTransition(async () => {
      await setLocale(next);
      router.refresh();
    });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label={t("locale")}
          data-testid="locale-switcher-trigger"
          disabled={pending}
        >
          <Languages className="h-4 w-4" aria-hidden />
          <span className="ml-1.5 font-medium uppercase tracking-wide">
            {LABELS[currentLocale].flag}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel>{t("locale")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {locales.map((loc) => {
          const active = loc === currentLocale;
          return (
            <DropdownMenuItem
              key={loc}
              data-testid={`locale-switcher-item-${loc}`}
              onSelect={(e) => {
                e.preventDefault();
                onPick(loc);
              }}
            >
              <span className="flex-1">{LABELS[loc].label}</span>
              {active ? <Check className="h-3.5 w-3.5" aria-hidden /> : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
