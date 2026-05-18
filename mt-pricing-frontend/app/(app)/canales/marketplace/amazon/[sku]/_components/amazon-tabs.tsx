"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

interface Props {
  sku: string;
}

export function AmazonTabs({ sku }: Props) {
  const pathname = usePathname() ?? "";
  const base = `/canales/marketplace/amazon/${sku}`;

  const tabs = [
    {
      href: base,
      label: "Datos Amazon",
      match: (p: string) => p === base,
    },
    {
      href: `${base}/contenido`,
      label: "Contenido Listing",
      match: (p: string) => p.startsWith(`${base}/contenido`),
    },
    {
      href: `${base}/validacion`,
      label: "Validación",
      match: (p: string) => p.startsWith(`${base}/validacion`),
    },
  ];

  return (
    <nav role="tablist" aria-label="Secciones del listing Amazon" className="border-b">
      <ul className="-mb-px flex items-center gap-1">
        {tabs.map((tab) => {
          const active = tab.match(pathname);
          return (
            <li key={tab.href} role="presentation">
              <Link
                href={tab.href}
                role="tab"
                aria-selected={active}
                className={cn(
                  "inline-flex items-center gap-1.5 border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  active
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
