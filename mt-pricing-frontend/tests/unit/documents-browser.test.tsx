import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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

const useDocumentsMock = vi.fn();
vi.mock("@/lib/hooks/use-documents", () => ({
  useDocuments: (...args: unknown[]) => useDocumentsMock(...args),
  useDocument: () => ({ data: undefined, isLoading: false, isError: false }),
  useCreateDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteDocument: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { DocumentsBrowser } from "@/components/domain/documents-browser";
import type { Document } from "@/lib/api/types-assets-extended";

function makeDoc(overrides: Partial<Document> & { id: string }): Document {
  const { id, ...rest } = overrides;
  return {
    id,
    type: "ficha_tecnica",
    code: "FT-001",
    version: "1.0",
    language: "es",
    asset_id: `asset-${id}`,
    issued_at: "2026-05-01",
    created_at: "2026-05-01T00:00:00Z",
    ...rest,
  } as Document;
}

function renderBrowser(
  props?: Partial<React.ComponentProps<typeof DocumentsBrowser>>,
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <DocumentsBrowser {...props} />
    </QueryClientProvider>,
  );
}

describe("DocumentsBrowser (Fase 4)", () => {
  beforeEach(() => {
    useDocumentsMock.mockReset();
  });

  it("muestra loading mientras isLoading=true", () => {
    useDocumentsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    renderBrowser();
    expect(screen.getByTestId("documents-loading")).toBeInTheDocument();
  });

  it("muestra empty cuando no hay documentos", () => {
    useDocumentsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderBrowser();
    expect(screen.getByTestId("documents-empty")).toBeInTheDocument();
  });

  it("renderiza una fila por documento", () => {
    useDocumentsMock.mockReturnValue({
      data: [
        makeDoc({ id: "doc-1", code: "FT-001" }),
        makeDoc({ id: "doc-2", code: "MAN-002", type: "manual" }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderBrowser();
    expect(screen.getByTestId("documents-row-doc-1")).toBeInTheDocument();
    expect(screen.getByTestId("documents-row-doc-2")).toBeInTheDocument();
    expect(screen.getByText("FT-001")).toBeInTheDocument();
    expect(screen.getByText("MAN-002")).toBeInTheDocument();
  });

  it("cambiar el filtro type re-invoca el hook con filtros", () => {
    useDocumentsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderBrowser();
    const select = screen.getByTestId("documents-filter-type") as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "manual" } });
    // Última llamada debe incluir type: 'manual'
    const lastCall = useDocumentsMock.mock.calls.at(-1);
    expect(lastCall?.[0]).toEqual({ type: "manual" });
  });

  it("el botón download apunta a /api/v1/assets/{asset_id}", () => {
    useDocumentsMock.mockReturnValue({
      data: [makeDoc({ id: "doc-1", asset_id: "asset-xyz" })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderBrowser();
    const dl = screen.getByTestId("documents-download-doc-1");
    expect(dl.tagName.toLowerCase()).toBe("a");
    expect(dl).toHaveAttribute("href", "/api/v1/assets/asset-xyz");
  });
});
