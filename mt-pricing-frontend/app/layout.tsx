import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { NuqsAdapter } from "nuqs/adapters/next/app";

import { I18nProvider } from "@/lib/providers/i18n-provider";
import { QueryProvider } from "@/lib/providers/query-provider";
import { AuthProvider } from "@/components/auth/auth-provider";
import { Toaster } from "@/components/ui/sonner";
import { resolveLocale } from "@/lib/i18n/cookie";
import { WebVitalsReporter } from "./_components/web-vitals-reporter";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-sans" });

export const metadata: Metadata = {
  title: "MT Pricing",
  description: "MT Pricing & MDM platform",
  icons: {
    icon: "/favicon.ico",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await resolveLocale();
  const messages = (await import(`@/messages/${locale}.json`)).default;

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen bg-background text-foreground`}>
        <I18nProvider locale={locale} messages={messages}>
          <QueryProvider>
            <AuthProvider>
              <NuqsAdapter>
                {children}
                <Toaster />
                <WebVitalsReporter />
              </NuqsAdapter>
            </AuthProvider>
          </QueryProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
