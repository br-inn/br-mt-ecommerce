import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as React from "react";

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

import { SparePartCompatibilityForm } from "@/components/domain/spare-part-compatibility-form";

describe("SparePartCompatibilityForm (Fase 5)", () => {
  it("oculta dn_min/dn_max cuando owner_type='product' (default)", () => {
    render(
      <SparePartCompatibilityForm sku="SKU-A" onSubmit={vi.fn()} />,
    );
    expect(screen.queryByTestId("dn-range-fields")).not.toBeInTheDocument();
  });

  it("muestra dn_min/dn_max al cambiar owner_type a 'series'", () => {
    render(
      <SparePartCompatibilityForm sku="SKU-A" onSubmit={vi.fn()} />,
    );
    const seriesRadio = screen.getByLabelText("Serie") as HTMLInputElement;
    fireEvent.click(seriesRadio);
    expect(screen.getByTestId("dn-range-fields")).toBeInTheDocument();
    expect(screen.getByLabelText("DN min")).toBeInTheDocument();
    expect(screen.getByLabelText("DN max")).toBeInTheDocument();
  });

  it("submit con owner_type='product' no envía dn_min/dn_max", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<SparePartCompatibilityForm sku="SKU-A" onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("SKU compatible"), {
      target: { value: "SKU-B" },
    });
    fireEvent.click(screen.getByRole("button", { name: /añadir enlace/i }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.compatible_with_sku).toBe("SKU-B");
    expect(payload.owner_type).toBe("product");
    expect(payload.dn_min).toBeUndefined();
    expect(payload.dn_max).toBeUndefined();
  });

  it("submit con owner_type='series' incluye dn_min/dn_max numéricos", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<SparePartCompatibilityForm sku="SKU-A" onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("SKU compatible"), {
      target: { value: "SKU-B" },
    });
    fireEvent.click(screen.getByLabelText("Serie"));
    fireEvent.change(screen.getByLabelText("DN min"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("DN max"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: /añadir enlace/i }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.owner_type).toBe("series");
    expect(payload.dn_min).toBe(20);
    expect(payload.dn_max).toBe(100);
  });

  it("valida que dn_max >= dn_min", async () => {
    const onSubmit = vi.fn();
    render(<SparePartCompatibilityForm sku="SKU-A" onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("SKU compatible"), {
      target: { value: "SKU-B" },
    });
    fireEvent.click(screen.getByLabelText("Serie"));
    fireEvent.change(screen.getByLabelText("DN min"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("DN max"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: /añadir enlace/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/dn_max debe ser >= dn_min/i);
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("bloquea self-loop (SKU compatible == sku origen)", async () => {
    const onSubmit = vi.fn();
    render(<SparePartCompatibilityForm sku="SKU-A" onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("SKU compatible"), {
      target: { value: "SKU-A" },
    });
    fireEvent.click(screen.getByRole("button", { name: /añadir enlace/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/consigo mismo/i);
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
