import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";

import { PreviewDiff } from "@/app/(app)/imports/_components/preview-diff";
import type { ImportPreview } from "@/lib/api/endpoints/imports";

const messages = {
  imports: {
    preview: {
      title: "Diff",
      confirm: "Confirmar",
      emptyBucket: "Vacío",
      summary: {
        creates: "Nuevos",
        updates: "Modificados",
        skipped: "Omitidos",
        errors: "Errores",
      },
      tabs: {
        creates: "Nuevos",
        updates: "Modificados",
        skipped: "Omitidos",
        errors: "Errores",
      },
    },
  },
  common: { back: "Atrás", loading: "…" },
};

const preview: ImportPreview = {
  run_id: "run-1",
  type: "pim",
  status: "preview_ready",
  filename: "PIM.xlsx",
  uploaded_at: "2026-05-07T00:00:00Z",
  summary: {
    total: 4,
    creates: 1,
    updates: 1,
    skipped_locked: 1,
    no_change: 0,
    errors: 1,
    orphans: 0,
  },
  progress: null,
  rows: [
    { row_index: 1, sku: "MTV-1", action: "create" },
    {
      row_index: 2,
      sku: "MTV-2",
      action: "update",
      diff: [{ field: "dn", before: "DN50", after: "DN65" }],
    },
    { row_index: 3, sku: "MTV-3", action: "skip_locked" },
    {
      row_index: 4,
      sku: "MTV-4",
      action: "error",
      error_code: "BR_1A_02",
      error_message: "Falta name_en",
    },
  ],
};

describe("PreviewDiff (US-1A-06-01 frontend)", () => {
  it("muestra summary cards y la fila de creación", () => {
    render(
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <PreviewDiff
          preview={preview}
          onConfirm={vi.fn()}
          onBack={vi.fn()}
        />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId("import-summary")).toBeInTheDocument();
    expect(screen.getByTestId("row-creates-MTV-1")).toBeInTheDocument();
  });

  it("dispara onConfirm al confirmar", async () => {
    const onConfirm = vi.fn();
    render(
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <PreviewDiff
          preview={preview}
          onConfirm={onConfirm}
          onBack={vi.fn()}
        />
      </NextIntlClientProvider>,
    );
    await userEvent.click(screen.getByTestId("import-confirm"));
    expect(onConfirm).toHaveBeenCalled();
  });
});
