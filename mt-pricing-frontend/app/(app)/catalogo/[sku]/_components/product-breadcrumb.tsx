"use client";

import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";

interface Props {
  sku: string;
}

const TAB_LABELS: Array<{ segment: string; label: string }> = [
  { segment: "mercados",     label: "Mercados"       },
  { segment: "imagenes",     label: "Imagenes"       },
  { segment: "traducciones", label: "Traducciones"   },
  { segment: "unidades",     label: "Unidades"       },
  { segment: "costos",       label: "Costos"         },
  { segment: "datasheets",   label: "Documentos"     },
  { segment: "recambios",    label: "Recambios"      },
  { segment: "audit",        label: "Auditoria"      },
  { segment: "edit",         label: "Editar"         },
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
      <span>{match.label}</span>
    </>
  );
}
