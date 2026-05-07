import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataQualityBadge } from "@/components/domain/data-quality-badge";
import type { DataQuality } from "@/lib/api/endpoints/products";

describe("DataQualityBadge", () => {
  const cases: { value: DataQuality; label: string }[] = [
    { value: "complete", label: "Complete" },
    { value: "partial", label: "Partial" },
    { value: "blocked", label: "Blocked" },
  ];

  it.each(cases)("renders the $value badge with the correct label", ({ value, label }) => {
    render(<DataQualityBadge value={value} />);
    const el = screen.getByTestId(`data-quality-${value}`);
    expect(el).toBeInTheDocument();
    expect(el).toHaveAccessibleName(label);
    expect(el).toHaveTextContent(label);
  });

  it("forwards extra className", () => {
    render(<DataQualityBadge value="complete" className="extra-class" />);
    const el = screen.getByTestId("data-quality-complete");
    expect(el.className).toContain("extra-class");
  });
});
