type Locale = "es" | "en";
type Currency = "AED" | "EUR" | "USD";

const LOCALE_MAP: Record<Locale, string> = {
  es: "es-ES",
  en: "en-US",
};

export function formatCurrency(
  amount: number,
  currency: Currency,
  locale: Locale = "es",
): string {
  return new Intl.NumberFormat(LOCALE_MAP[locale], {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(value: number, locale: Locale = "es"): string {
  return new Intl.NumberFormat(LOCALE_MAP[locale]).format(value);
}

export function formatDate(
  value: Date | string | number,
  locale: Locale = "es",
  options: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "2-digit",
  },
): string {
  const date = value instanceof Date ? value : new Date(value);
  return new Intl.DateTimeFormat(LOCALE_MAP[locale], options).format(date);
}

export function formatDateTime(
  value: Date | string | number,
  locale: Locale = "es",
): string {
  return formatDate(value, locale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatPercent(value: number, locale: Locale = "es"): string {
  return new Intl.NumberFormat(LOCALE_MAP[locale], {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(value);
}
