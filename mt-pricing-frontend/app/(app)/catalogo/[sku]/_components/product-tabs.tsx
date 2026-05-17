"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Props {
  sku: string;
  /** Si el producto no tiene imagen principal, se muestra alerta en tab Imágenes */
  hasImage?: boolean;
}

/**
 * Tabs URL-driven con overflow. 5 tabs primarios visibles + dropdown para los
 * tabs operacionales menos frecuentes.
 */
export function ProductTabs({ sku, hasImage = true }: Props) {
  const pathname = usePathname() ?? "";

  const primaryTabs = [
    {
      href: `/catalogo/${sku}`,
      label: "Specs",
      match: (p: string) => p === `/catalogo/${sku}`,
    },
    {
      href: `/catalogo/${sku}/mercados`,
      label: "Mercados",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/mercados`),
    },
    {
      href: `/catalogo/${sku}/imagenes`,
      label: "Imágenes",
      badge: !hasImage ? "⚠" : undefined,
      match: (p: string) => p.startsWith(`/catalogo/${sku}/imagenes`),
    },
    {
      href: `/catalogo/${sku}/traducciones`,
      label: "Traducciones",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/traducciones`),
    },
    {
      href: `/catalogo/${sku}/datasheets`,
      label: "Datasheets",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/datasheets`),
    },
  ];

  const overflowTabs = [
    {
      href: `/catalogo/${sku}/unidades`,
      label: "Unidades",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/unidades`),
    },
    {
      href: `/catalogo/${sku}/costos`,
      label: "Costos",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/costos`),
    },
    {
      href: `/catalogo/${sku}/recambios`,
      label: "Recambios",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/recambios`),
    },
    {
      href: `/catalogo/${sku}/audit`,
      label: "Auditoría",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/audit`),
    },
    {
      href: `/catalogo/${sku}/enriquecer`,
      label: "Enriquecer",
      match: (p: string) => p.startsWith(`/catalogo/${sku}/enriquecer`),
    },
  ];

  // ¿Algún tab del overflow está activo? Si es así, el botón ··· se activa también.
  const overflowActive = overflowTabs.some((t) => t.match(pathname));
  const activeOverflowTab = overflowTabs.find((t) => t.match(pathname));

  return (
    <nav
      role="tablist"
      aria-label="Secciones del producto"
      className="border-b"
    >
      <ul className="-mb-px flex items-center gap-1">
        {/* Tabs primarios */}
        {primaryTabs.map((tab) => {
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
                {tab.badge ? (
                  <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-700">
                    {tab.badge}
                  </span>
                ) : null}
              </Link>
            </li>
          );
        })}

        {/* Overflow dropdown */}
        <li role="presentation" className="ml-1">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                role="tab"
                aria-selected={overflowActive}
                className={cn(
                  "inline-flex items-center gap-1 border-b-2 px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  overflowActive
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {overflowActive && activeOverflowTab
                  ? activeOverflowTab.label
                  : <MoreHorizontal className="h-4 w-4" />}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {overflowTabs.map((tab) => {
                const active = tab.match(pathname);
                return (
                  <DropdownMenuItem key={tab.href} asChild>
                    <Link
                      href={tab.href}
                      className={cn(
                        "w-full",
                        active && "font-semibold text-foreground",
                      )}
                    >
                      {tab.label}
                    </Link>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </li>
      </ul>
    </nav>
  );
}
