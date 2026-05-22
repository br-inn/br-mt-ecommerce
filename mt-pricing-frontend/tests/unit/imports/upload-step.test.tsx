import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider } from "next-intl";

vi.mock("@/lib/env", () => ({
  default: {
    NEXT_PUBLIC_SUPABASE_URL: "https://example.supabase.co",
    NEXT_PUBLIC_SUPABASE_KEY: "anon-test",
    NEXT_PUBLIC_BACKEND_URL: "http://localhost:8000",
  },
}));
vi.mock("@/lib/supabase/client", () => ({
  createSupabaseBrowserClient: () => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  }),
}));

import { importsApi, type ImportPreview } from "@/lib/api/endpoints/imports";
import { UploadStep } from "@/app/(app)/imports/_components/upload-step";

const messages = {
  imports: {
    upload: {
      title: "Sube",
      hint: "—",
      limits: "≤ 50 MB",
      dropLabel: "Drop",
      remove: "Quitar",
      startPreview: "Generar",
      uploading: "Subiendo…",
      errors: {
        tooLarge: "Demasiado grande",
        invalidFormat: "Formato inválido",
      },
    },
  },
  common: { error: "Error", loading: "…" },
};

const samplePreview: ImportPreview = {
  run_id: "run-1",
  type: "pim",
  status: "preview_ready",
  filename: "PIM.xlsx",
  uploaded_at: "2026-05-07T00:00:00Z",
  summary: {
    total: 10,
    creates: 5,
    updates: 3,
    skipped_locked: 0,
    no_change: 1,
    errors: 1,
    orphans: 0,
  },
  progress: null,
  rows: [],
};

function renderStep(onAnalyzed = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return {
    onAnalyzed,
    ...render(
      <QueryClientProvider client={client}>
        <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
          <UploadStep onAnalyzed={onAnalyzed} />
        </NextIntlClientProvider>
      </QueryClientProvider>,
    ),
  };
}

describe("UploadStep (US-1A-06-01 frontend)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("sube archivo válido y llama onAnalyzed con el preview", async () => {
    const spy = vi.spyOn(importsApi, "preview").mockResolvedValue(samplePreview);
    const { onAnalyzed } = renderStep();
    const file = new File(["xls-bytes"], "PIM.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const input = document.querySelector(
      "[data-testid='import-file-input']",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() =>
      expect(screen.getByTestId("import-file-preview")).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByTestId("import-upload-submit"));

    await waitFor(() => expect(spy).toHaveBeenCalled());
    await waitFor(() =>
      expect(onAnalyzed).toHaveBeenCalledWith(samplePreview),
    );
  });

  it("rechaza archivo > 50 MB sin disparar el upload", async () => {
    const spy = vi.spyOn(importsApi, "preview").mockResolvedValue(samplePreview);
    renderStep();
    const big = new File([new Uint8Array(51 * 1024 * 1024)], "PIM.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const input = document.querySelector(
      "[data-testid='import-file-input']",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [big] } });
    // No file preview porque la validación lo rechazó.
    await waitFor(() => {
      expect(screen.queryByTestId("import-file-preview")).not.toBeInTheDocument();
    });
    expect(spy).not.toHaveBeenCalled();
  });
});
