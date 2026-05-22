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

import {
  importsApi,
  type AnalyzeImportResponse,
} from "@/lib/api/endpoints/imports";
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

const sampleAnalysis: AnalyzeImportResponse = {
  filename: "PIM.xlsx",
  detected_header_row: 0,
  headers: ["SKU", "Name"],
  sample_rows: [["SKU-001", "Product 1"]],
  proposed_mapping: [],
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
    const spy = vi.spyOn(importsApi, "analyze").mockResolvedValue(sampleAnalysis);
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
      expect(onAnalyzed).toHaveBeenCalledWith(sampleAnalysis, expect.any(File)),
    );
  });

  it("rechaza archivo > 50 MB sin disparar el upload", async () => {
    const spy = vi.spyOn(importsApi, "analyze").mockResolvedValue(sampleAnalysis);
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
