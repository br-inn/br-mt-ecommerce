import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

import { dimensionsApi } from "@/lib/api/endpoints/dimensions";
import {
  DimensionTable,
  formatColumnHeader,
  renderCellValue,
  resolveActuationLabel,
} from "@/components/domain/dimension-table";
import type {
  ActuationCode,
  DimensionColumn,
  DimensionTableResponse,
} from "@/lib/api/types-dimensions";

const SKU = "MT-V-001";
const FAMILY_ID = "11111111-1111-1111-1111-111111111111";

function makeColumn(over: Partial<DimensionColumn>): DimensionColumn {
  return {
    id: "col-1",
    family_id: FAMILY_ID,
    code: "a",
    label_en: "A",
    unit: "mm",
    order_index: 0,
    ...over,
  };
}

function renderTable() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    React.createElement(
      QueryClientProvider,
      { client },
      React.createElement(DimensionTable, { sku: SKU }),
    ),
  );
}

describe("DimensionTable — helpers", () => {
  it("formatColumnHeader appends the unit in parentheses", () => {
    expect(
      formatColumnHeader(makeColumn({ label_en: "A", unit: "mm" })),
    ).toBe("A (mm)");
    expect(
      formatColumnHeader(makeColumn({ label_en: "Weight", unit: "kg" })),
    ).toBe("Weight (kg)");
    expect(
      formatColumnHeader(makeColumn({ label_en: "Notes", unit: null })),
    ).toBe("Notes");
  });

  it("renderCellValue formats numeric kg cells with 3 decimals and others with 2", () => {
    expect(
      renderCellValue(
        {
          id: "c1",
          row_id: "r1",
          column_id: "c1",
          value_number: 12.345678,
          value_text: null,
        },
        makeColumn({ unit: "mm" }),
      ),
    ).toBe("12.35");
    expect(
      renderCellValue(
        {
          id: "c1",
          row_id: "r1",
          column_id: "c1",
          value_number: 0.123456,
          value_text: null,
        },
        makeColumn({ unit: "kg" }),
      ),
    ).toBe("0.123");
  });

  it("renderCellValue returns text values verbatim and em-dash for empty cells", () => {
    expect(
      renderCellValue(
        {
          id: "c2",
          row_id: "r1",
          column_id: "c2",
          value_number: null,
          value_text: "ANSI 150",
        },
        makeColumn({ unit: null }),
      ),
    ).toBe("ANSI 150");
    expect(renderCellValue(undefined, makeColumn({}))).toBe("—");
  });

  it("resolveActuationLabel looks up the catalogue by id", () => {
    const cat: ActuationCode[] = [
      {
        id: "act-1",
        code: "M1",
        name_en: "Manual handle",
        type: "handle",
      },
      {
        id: "act-2",
        code: "G1",
        name_en: "Gearbox",
        type: "gearbox",
      },
    ];
    expect(resolveActuationLabel("act-2", cat)).toBe("G1");
    expect(resolveActuationLabel("nope", cat)).toBe("—");
    expect(resolveActuationLabel(null, cat)).toBe("—");
  });
});

describe("DimensionTable — render", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the placeholder when the table has no rows", async () => {
    vi.spyOn(dimensionsApi, "getProductDimensions").mockResolvedValue({
      product_sku: SKU,
      family_id: FAMILY_ID,
      columns: [],
      rows: [],
    } satisfies DimensionTableResponse);
    vi.spyOn(dimensionsApi, "listActuationCodes").mockResolvedValue([]);

    renderTable();

    await waitFor(() =>
      expect(
        screen.getByText(/Sin tabla dimensional configurada/i),
      ).toBeInTheDocument(),
    );
  });

  it("renders headers, ordered rows and looks up actuation codes", async () => {
    const columns: DimensionColumn[] = [
      makeColumn({
        id: "col-A",
        code: "a",
        label_en: "A",
        unit: "mm",
        order_index: 1,
      }),
      makeColumn({
        id: "col-Wt",
        code: "wt",
        label_en: "Weight",
        unit: "kg",
        order_index: 0,
      }),
    ];
    vi.spyOn(dimensionsApi, "getProductDimensions").mockResolvedValue({
      product_sku: SKU,
      family_id: FAMILY_ID,
      columns,
      rows: [
        {
          id: "row-2",
          product_sku: SKU,
          size_label: "2\"",
          dn: 50,
          actuation_code_id: "act-1",
          order_index: 1,
          cells: [
            {
              id: "ce-2A",
              row_id: "row-2",
              column_id: "col-A",
              value_number: 165,
              value_text: null,
            },
            {
              id: "ce-2W",
              row_id: "row-2",
              column_id: "col-Wt",
              value_number: 4.5,
              value_text: null,
            },
          ],
        },
        {
          id: "row-1",
          product_sku: SKU,
          size_label: "1\"",
          dn: 25,
          actuation_code_id: "act-1",
          order_index: 0,
          cells: [
            {
              id: "ce-1A",
              row_id: "row-1",
              column_id: "col-A",
              value_number: 100,
              value_text: null,
            },
            {
              id: "ce-1W",
              row_id: "row-1",
              column_id: "col-Wt",
              value_number: 1.234,
              value_text: null,
            },
          ],
        },
      ],
    } satisfies DimensionTableResponse);
    vi.spyOn(dimensionsApi, "listActuationCodes").mockResolvedValue([
      {
        id: "act-1",
        code: "M1",
        name_en: "Manual handle",
        type: "handle",
      },
    ]);

    renderTable();

    await waitFor(() => {
      // Headers respect order_index — Weight first, then A.
      expect(screen.getByText("Weight (kg)")).toBeInTheDocument();
      expect(screen.getByText("A (mm)")).toBeInTheDocument();
    });

    // Body rows in order_index order (1" before 2").
    const rows = screen.getAllByRole("row");
    // first row = header, then 1" then 2".
    const row1 = rows[1];
    const row2 = rows[2];
    if (!row1 || !row2) throw new Error("Expected at least 3 rendered rows.");
    expect(within(row1).getByText('1"')).toBeInTheDocument();
    expect(within(row2).getByText('2"')).toBeInTheDocument();

    // Actuation code resolved to its catalogue label.
    expect(screen.getAllByText("M1").length).toBeGreaterThanOrEqual(2);

    // kg formatted with 3 decimals; mm with 2.
    expect(screen.getByText("1.234")).toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
  });

  it("renders text cell values verbatim and em-dash for missing cells", async () => {
    const columns: DimensionColumn[] = [
      makeColumn({
        id: "col-flange",
        code: "flange",
        label_en: "Flange",
        unit: null,
        order_index: 0,
      }),
      makeColumn({
        id: "col-A",
        code: "a",
        label_en: "A",
        unit: "mm",
        order_index: 1,
      }),
    ];
    vi.spyOn(dimensionsApi, "getProductDimensions").mockResolvedValue({
      product_sku: SKU,
      family_id: FAMILY_ID,
      columns,
      rows: [
        {
          id: "row-1",
          product_sku: SKU,
          size_label: "1\"",
          dn: 25,
          actuation_code_id: null,
          order_index: 0,
          cells: [
            {
              id: "ce-1F",
              row_id: "row-1",
              column_id: "col-flange",
              value_number: null,
              value_text: "ANSI 150",
            },
            // No cell for col-A — should render em-dash.
          ],
        },
      ],
    } satisfies DimensionTableResponse);
    vi.spyOn(dimensionsApi, "listActuationCodes").mockResolvedValue([]);

    renderTable();

    await waitFor(() =>
      expect(screen.getByText("ANSI 150")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });
});
