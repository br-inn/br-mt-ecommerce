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

const useAssetLinksForOwnerMock = vi.fn();
vi.mock("@/lib/hooks/use-asset-links", () => ({
  useAssetLinksForOwner: (...args: unknown[]) =>
    useAssetLinksForOwnerMock(...args),
  useCreateAssetLink: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteAssetLink: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { AssetGalleryPolymorphic } from "@/components/domain/asset-gallery-polymorphic";
import type { AssetLinkWithAsset } from "@/lib/api/types-assets-extended";

function makeLink(
  overrides: Partial<AssetLinkWithAsset> & { id: string; role: AssetLinkWithAsset["role"] },
): AssetLinkWithAsset {
  const { id, role, ...rest } = overrides;
  return {
    id,
    asset_id: `asset-${id}`,
    owner_type: "product",
    owner_id: "MTV-1",
    role,
    order_index: 0,
    created_at: "2026-05-01T00:00:00Z",
    asset: {
      id: `asset-${id}`,
      sku: "MTV-1",
      kind: "photo",
      bucket: "product-images",
      storage_path: `path/${id}.png`,
      original_url: `https://cdn/${id}.png`,
      is_primary: false,
      position: 0,
      alt_text: `alt-${id}`,
      status: "active",
      created_at: "2026-05-01T00:00:00Z",
      urls: {
        original: `https://cdn/${id}.png`,
        thumb_400: `https://cdn/${id}-400.png`,
      },
    },
    ...rest,
  } as AssetLinkWithAsset;
}

function renderGallery(props?: Partial<React.ComponentProps<typeof AssetGalleryPolymorphic>>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AssetGalleryPolymorphic ownerType="product" ownerId="MTV-1" {...props} />
    </QueryClientProvider>,
  );
}

describe("AssetGalleryPolymorphic (Fase 4)", () => {
  beforeEach(() => {
    useAssetLinksForOwnerMock.mockReset();
  });

  it("muestra estado loading mientras isLoading=true", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    expect(screen.getByTestId("asset-gallery-loading")).toBeInTheDocument();
  });

  it("muestra empty cuando data=[]", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    expect(screen.getByTestId("asset-gallery-empty")).toBeInTheDocument();
  });

  it("renderiza tabs agrupados por role", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [
        makeLink({ id: "1", role: "image_padre", order_index: 0 }),
        makeLink({ id: "2", role: "ficha_pdf", order_index: 0 }),
        makeLink({ id: "3", role: "video", order_index: 0 }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    expect(screen.getByTestId("asset-gallery-tab-image_padre")).toBeInTheDocument();
    expect(screen.getByTestId("asset-gallery-tab-ficha_pdf")).toBeInTheDocument();
    expect(screen.getByTestId("asset-gallery-tab-video")).toBeInTheDocument();
  });

  it("filtra por allowedRoles cuando se provee", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [
        makeLink({ id: "1", role: "image_padre" }),
        makeLink({ id: "2", role: "ficha_pdf" }),
        makeLink({ id: "3", role: "video" }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery({ allowedRoles: ["image_padre"] });
    expect(screen.getByTestId("asset-gallery-tab-image_padre")).toBeInTheDocument();
    expect(screen.queryByTestId("asset-gallery-tab-ficha_pdf")).not.toBeInTheDocument();
    expect(screen.queryByTestId("asset-gallery-tab-video")).not.toBeInTheDocument();
  });

  it("ordena items por order_index", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [
        makeLink({ id: "b", role: "image_padre", order_index: 5 }),
        makeLink({ id: "a", role: "image_padre", order_index: 1 }),
      ],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    const thumbs = screen.getAllByRole("button", { name: /preview/i });
    // Primer thumb debe ser el de order_index=1 (id="a")
    expect(thumbs[0]).toHaveAttribute("data-testid", "asset-thumb-a");
  });

  it("renderiza botón Download PDF para roles pdf", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [makeLink({ id: "1", role: "ficha_pdf" })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    const link = screen.getByTestId("asset-download-1");
    expect(link.tagName.toLowerCase()).toBe("a");
    expect(link).toHaveAttribute("href", "https://cdn/1.png");
  });

  it("abre dialog de preview al clickear un thumbnail", () => {
    useAssetLinksForOwnerMock.mockReturnValue({
      data: [makeLink({ id: "1", role: "image_padre" })],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderGallery();
    fireEvent.click(screen.getByTestId("asset-thumb-1"));
    // Radix dialog usa role=dialog
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
