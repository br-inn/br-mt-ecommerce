"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

interface Props {
  sku: string;
}

// Maps URL segments to display labels for the breadcrumb (UX-08)
const TAB_LABELS: Array<{ segment: string; label: string }> = [
  { segment: "especificaciones", label: "Especificaciones" },
  { segment: "mercados",         label: "Mercados"         },
  { segment: "imagenes",         label: "Imágenes"         },
  { segment: "traducciones",     label: "Traducciones"     },
  { segment: "unidades",         label: "Unidades"         },
  { segment: "costos",           label: "Costos"           },
  { segment: "datasheets",       label: "Documentos"       },
  { segment: "recambios",        label: "Recambios"        },
  { segment: "audit",            label: "Auditoría"        },
  { segment: "enrich",           label: "Enriquecer"       },
  { segment: "edit",             label: "Editar"           },
];

export function ProductBreadcrumb({ sku }: Props) {
  const pathname = usePathname() ?? "";

  const match = TAB_LABELS.find((tab) =>
    pathname.startsWith(`/catalogo/${sku}/${tab.segment}`)
  );

  if (!match) return null;

  return (
    <>
      <ChevronRight className="h-3.5 w-3.5 shrink-0" />
      <Link
        href={`/catalogo/${sku}/${match.segment}`}
        className="text-foreground"
        aria-current="page"
      >
        {match.label}
      </Link>
    </>
  );
}
