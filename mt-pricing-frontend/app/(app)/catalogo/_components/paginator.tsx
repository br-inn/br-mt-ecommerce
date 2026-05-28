"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight, RefreshCcw } from "lucide-react";
import { MT } from "@/components/mt/tokens";

interface PaginatorProps {
  page: number;
  pages: number | null;
  total: number | null;
  pageSize: number;
  onPageSize: (size: number) => void;
  onPage: (page: number) => void;
  isFetching?: boolean;
}

/**
 * Offset-based paginator: shows page X / Y, total count, prev/next arrows.
 */
export function Paginator({
  page,
  pages,
  total,
  pageSize,
  onPageSize,
  onPage,
  isFetching = false,
}: PaginatorProps) {
  const hasPrev = page > 1;
  const hasNext = pages !== null ? page < pages : false;

  return (
    <div
      className="flex items-center justify-between gap-3 border-t px-4 py-1.5 text-[11.5px]"
      style={{ borderColor: MT.border, background: MT.surface, color: MT.ink3 }}
    >
      <span className="mt-mono tabular-nums">
        {total !== null ? (
          <>
            <strong style={{ color: MT.ink }}>{total.toLocaleString()}</strong>{" "}
            resultados
          </>
        ) : null}
      </span>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1">
          <span style={{ color: MT.ink4 }}>por página</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value))}
            className="rounded-sm border bg-transparent px-1 py-0.5 text-[11.5px] outline-none"
            style={{ borderColor: MT.border, color: MT.ink }}
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </label>

        <button
          type="button"
          disabled={!hasPrev || isFetching}
          onClick={() => onPage(page - 1)}
          className="flex size-6 items-center justify-center rounded-sm hover:bg-mt-surface2
                     disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Página anterior"
        >
          <ChevronLeft className="size-3.5" />
        </button>

        <span
          className="mt-mono tabular-nums min-w-[5.5rem] text-center"
          style={{ color: MT.ink }}
        >
          {isFetching ? (
            <RefreshCcw className="inline size-3 animate-spin" />
          ) : (
            <>
              pág. <strong>{page}</strong>
              {pages !== null ? <> / {pages}</> : null}
            </>
          )}
        </span>

        <button
          type="button"
          disabled={!hasNext || isFetching}
          onClick={() => onPage(page + 1)}
          className="flex size-6 items-center justify-center rounded-sm hover:bg-mt-surface2
                     disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Página siguiente"
        >
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
