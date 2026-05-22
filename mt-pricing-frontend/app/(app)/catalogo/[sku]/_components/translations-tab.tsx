"use client";

import { useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useCompleteTranslations } from "@/lib/hooks/imports/use-translation-coverage";

// ---- Constants --------------------------------------------------------------

const LANGS = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "pt", label: "Português" },
  { code: "ar", label: "العربية" },
] as const;

type LangCode = (typeof LANGS)[number]["code"];

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  imported: "Importado",
  ai_generated: "IA",
  reviewed: "Revisado",
  draft: "Borrador",
  approved: "Aprobado",
};

// ---- Types ------------------------------------------------------------------

export interface TranslationRow {
  lang: string;
  name: string | null;
  status: string;
}

interface Props {
  sku: string;
  translations: TranslationRow[];
}

// ---- Component --------------------------------------------------------------

export function TranslationsTab({ sku, translations }: Props) {
  const [selected, setSelected] = useState<LangCode[]>([]);
  const mutation = useCompleteTranslations();

  const translationsByLang = Object.fromEntries(
    translations.map((t) => [t.lang, t]),
  );

  const missingLangs = LANGS.filter((l) => !translationsByLang[l.code]?.name);
  const completedCount = LANGS.length - missingLangs.length;

  function toggleLang(code: LangCode, checked: boolean | "indeterminate") {
    setSelected((prev) =>
      checked ? [...prev, code] : prev.filter((l) => l !== code),
    );
  }

  function handleComplete() {
    mutation.mutate(
      { skus: [sku], target_langs: selected },
      {
        onSuccess: () => setSelected([]),
      },
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {completedCount} / {LANGS.length} idiomas con nombre completado
      </p>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 text-left w-32">Idioma</th>
            <th className="py-2 text-left">Nombre</th>
            <th className="py-2 text-left w-28">Estado</th>
          </tr>
        </thead>
        <tbody>
          {LANGS.map(({ code, label }) => {
            const t = translationsByLang[code];
            return (
              <tr key={code} className="border-b last:border-0">
                <td className="py-2 font-medium">{label}</td>
                <td className="py-2 text-muted-foreground">
                  {t?.name ?? (
                    <span className="italic text-muted-foreground/60">
                      Sin traducción
                    </span>
                  )}
                </td>
                <td className="py-2">
                  <Badge variant="outline">
                    {STATUS_LABELS[t?.status ?? "pending"] ??
                      t?.status ??
                      "Pendiente"}
                  </Badge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {missingLangs.length > 0 && (
        <div className="rounded-lg border p-4 space-y-3">
          <p className="text-sm font-medium">Completar con IA</p>
          <div className="flex flex-wrap gap-3">
            {missingLangs.map(({ code, label }) => (
              <label
                key={code}
                className="flex items-center gap-2 text-sm cursor-pointer"
              >
                <Checkbox
                  checked={selected.includes(code)}
                  onCheckedChange={(v) => toggleLang(code, v)}
                />
                {label}
              </label>
            ))}
          </div>
          <Button
            size="sm"
            disabled={selected.length === 0 || mutation.isPending}
            onClick={handleComplete}
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 mr-2" />
            )}
            Completar seleccionados
          </Button>
          {mutation.isSuccess && (
            <p className="text-sm text-green-600">
              {mutation.data.completed} traducciones completadas
              {mutation.data.errors > 0 && (
                <span className="text-amber-600 ml-2">
                  ({mutation.data.errors} con errores)
                </span>
              )}
            </p>
          )}
          {mutation.isError && (
            <p className="text-sm text-red-600">
              Error al completar traducciones. Intenta de nuevo.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
