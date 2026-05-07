"use client";

import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import type { ReactNode } from "react";
import type { Locale } from "@/lib/i18n/config";

interface I18nProviderProps {
  locale: Locale;
  /** Messages tree de next-intl. Typed as the lib's AbstractIntlMessages. */
  messages: AbstractIntlMessages;
  children: ReactNode;
}

export function I18nProvider({ locale, messages, children }: I18nProviderProps) {
  return (
    <NextIntlClientProvider locale={locale} messages={messages} timeZone="Europe/Madrid">
      {children}
    </NextIntlClientProvider>
  );
}
