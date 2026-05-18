"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight, RefreshCcw } from "lucide-react";

import { MT } from "@/components/mt/tokens";

interface PaginatorProps {
  loaded: number;
  total: number | null;
  pageSize: number;
  onPageSize: (size: number) => void;
  hasNext: boolean;
  onNext: () => void;
  onPrev?: () => void;
  isFetching?: boolean;
}

/**
 * Cursor-based "load more" paginator with page size selector.
 * Backend uses cursors not offsets so we don't expose page numbers.
 */
export function Paginator({
  loaded,
  total,
  pageSize,
  onPageSize,
  hasNext,
  onNext,
  onPrev,
  isFetching = false,
}: PaginatorProps) {
  return (
    <div
      className="flex items-center justify-between gap-3 border-t px-4 py-1.5 text-[11.5px]"
      style={{ borderColor: MT.border, background: MT.surface, color: MT.ink3 }}
    >
      <span className="mt-mono tabular-nums">
        {total !== null ? (
          <>
            mostrando <strong style={{ color: MT.ink }}>{loaded.toLocaleString()}</strong> de{" "}
            <strong style={{ color: MT.ink }}>{total.toLocaleString()}</strong>
          </>
        ) : (
          <>
            mostrando <strong style={{ color: MT.ink }}>{loaded.toLocaleString()}</strong>
          </>
        )}
      </span>

      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1">
          <span style={{ color: MT.ink4 }}>tamaño</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSize(Number(e.target.value))}
            className="rounded-sm border bg-transparent px-1 py-0.5 text-[11.5px] outline-none"
            style={{ borderColor: MT.border, color: MT.ink }}
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={250}>250</option>
          </select>
        </label>

        {onPrev ? (
          <button
            type="button"
            onClick={onPrev}
            className="flex size-6 items-center justify-center rounded-sm hover:bg-mt-surface2"
            aria-label="Anterior"
          >
            <ChevronLeft className="size-3.5" />
          </button>
        ) : null}

        <button
          type="button"
          disabled={!hasNext || isFetching}
          onClick={onNext}
          className="flex items-center gap-1 rounded-sm px-2 py-0.5 hover:bg-mt-surface2 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ color: hasNext ? MT.ink : MT.ink4 }}
        >
          {isFetching ? <RefreshCcw className="size-3 animate-spin" /> : <ChevronRight className="size-3.5" />}
          <span>cargar más</span>
        </button>
      </div>
    </div>
  );
}
