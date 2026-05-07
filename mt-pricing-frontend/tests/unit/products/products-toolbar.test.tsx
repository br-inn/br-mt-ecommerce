import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

const replaceMock = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
  useSearchParams: () => searchParams,
  usePathname: () => "/products",
}));

import { ProductsToolbar } from "@/app/(app)/products/_components/products-toolbar";

const messages = {
  catalog: {
    search: "Buscar",
    filters: {
      family: "Familia",
      anyFamily: "Cualquier familia",
      dataQuality: "Calidad",
      anyQuality: "Cualquier calidad",
      status: "Estado",
      anyStatus: "Cualquier estado",
      active: "Activos",
      inactive: "Inactivos",
      clear: "Limpiar",
      more: "Más filtros",
      advancedHint: "—",
      apply: "Aplicar",
      remove: "Quitar",
      dn: "DN",
      pn: "PN",
      material: "Material",
      title: "Filtros",
      createdAfter: "Desde",
      createdBefore: "Hasta",
    },
  },
};

describe("ProductsToolbar (US-1A-02-09 frontend)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    replaceMock.mockReset();
    searchParams = new URLSearchParams();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounce 300ms en búsqueda antes de actualizar URL", () => {
    render(
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <ProductsToolbar />
      </NextIntlClientProvider>,
    );
    const input = screen.getByTestId("products-search") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "valve" } });
    // Aún no se ha llamado.
    expect(replaceMock).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(310);
    });
    expect(replaceMock).toHaveBeenCalledTimes(1);
    expect(replaceMock.mock.calls[0]?.[0]).toContain("q=valve");
  });

  it("expone el botón 'Más filtros' y deja escribir DN dentro del Sheet", async () => {
    render(
      <NextIntlClientProvider locale="es" messages={messages} timeZone="UTC">
        <ProductsToolbar />
      </NextIntlClientProvider>,
    );
    expect(screen.getByTestId("products-more-filters")).toBeInTheDocument();
  });
});
