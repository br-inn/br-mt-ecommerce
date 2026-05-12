"use client";

import * as React from "react";
import { Download, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils/cn";
import { useDocuments } from "@/lib/hooks/use-documents";
import type {
  Document,
  DocumentType,
} from "@/lib/api/types-assets-extended";

interface Props {
  defaultType?: DocumentType;
  defaultLanguage?: string;
  className?: string;
}

const DOCUMENT_TYPES: DocumentType[] = [
  "ficha_tecnica",
  "manual",
  "declaracion_ce",
  "certificado",
  "catalogo",
];

const LANGUAGES = ["en", "es", "ar", "fr", "de", "it"];

function typeLabel(t: DocumentType): string {
  switch (t) {
    case "ficha_tecnica":
      return "Ficha técnica";
    case "manual":
      return "Manual";
    case "declaracion_ce":
      return "Declaración CE";
    case "certificado":
      return "Certificado";
    case "catalogo":
      return "Catálogo";
    default:
      return t;
  }
}

function languageFlag(lang: string): string {
  // Indicador textual sin emojis (project preferencia).
  return lang.toUpperCase();
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export function DocumentsBrowser({
  defaultType,
  defaultLanguage,
  className,
}: Props) {
  const [type, setType] = React.useState<DocumentType | "">(defaultType ?? "");
  const [language, setLanguage] = React.useState<string>(defaultLanguage ?? "");

  const filters = React.useMemo(
    () => ({
      ...(type ? { type } : {}),
      ...(language ? { language } : {}),
    }),
    [type, language],
  );

  const { data, isLoading, isError, refetch } = useDocuments(filters);
  const documents: Document[] = data ?? [];

  return (
    <div
      className={cn("space-y-4", className)}
      data-testid="documents-browser"
    >
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="documents-type"
            className="text-xs uppercase tracking-wide text-muted-foreground"
          >
            Tipo
          </label>
          <select
            id="documents-type"
            data-testid="documents-filter-type"
            value={type}
            onChange={(e) => setType(e.target.value as DocumentType | "")}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">Todos</option>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {typeLabel(t)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="documents-language"
            className="text-xs uppercase tracking-wide text-muted-foreground"
          >
            Idioma
          </label>
          <select
            id="documents-language"
            data-testid="documents-filter-language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="">Todos</option>
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {languageFlag(l)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2" data-testid="documents-loading">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded" />
          ))}
        </div>
      ) : isError ? (
        <div
          className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
          data-testid="documents-error"
        >
          <p>Error cargando documentos.</p>
          <Button variant="link" onClick={() => refetch()}>
            Reintentar
          </Button>
        </div>
      ) : documents.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-12 text-center text-sm text-muted-foreground"
          data-testid="documents-empty"
        >
          <FileText className="h-10 w-10" aria-hidden />
          <p>Sin documentos.</p>
        </div>
      ) : (
        <Table data-testid="documents-table">
          <TableHeader>
            <TableRow>
              <TableHead>Tipo</TableHead>
              <TableHead>Código</TableHead>
              <TableHead>Versión</TableHead>
              <TableHead>Idioma</TableHead>
              <TableHead>Emitido</TableHead>
              <TableHead className="text-right">Acciones</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.id} data-testid={`documents-row-${doc.id}`}>
                <TableCell>
                  <Badge variant="secondary">{typeLabel(doc.type)}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{doc.code}</TableCell>
                <TableCell>{doc.version}</TableCell>
                <TableCell>
                  <Badge variant="outline">{languageFlag(doc.language)}</Badge>
                </TableCell>
                <TableCell>{formatDate(doc.issued_at)}</TableCell>
                <TableCell className="text-right">
                  <Button
                    asChild
                    size="sm"
                    variant="outline"
                    data-testid={`documents-download-${doc.id}`}
                  >
                    <a
                      href={`/api/v1/assets/${doc.asset_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Download className="mr-1 h-3 w-3" aria-hidden />
                      Download
                    </a>
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
