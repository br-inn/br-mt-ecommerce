"use client";

import { useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useFamilyAttributes,
  useProductAttributes,
} from "@/lib/hooks/use-product-attributes";
import type {
  AttributeOption,
  AttributeValue,
  FamilyAttribute,
} from "@/lib/api/types-attributes";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ProductSpecsCardEAVProps {
  sku: string;
  /**
   * UUID of the product's family. May be null/undefined for legacy products
   * that have not yet been migrated to the family UUID FK — in that case the
   * card degrades to an explanatory empty state.
   */
  familyId: string | null | undefined;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Convert `ball_general` → `Ball general`. Conservative formatting: replaces
 * underscores with spaces and capitalises the first character only.
 */
export function humaniseGroupCode(code: string): string {
  if (!code) return "";
  const spaced = code.replace(/_/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Render an AttributeValue payload according to the attribute's data_type.
 * Returns the React node (or null when there is no value at all).
 */
export function renderAttributeValue(
  fa: FamilyAttribute,
  value: AttributeValue | undefined,
): React.ReactNode {
  const dataType = fa.definition?.data_type;
  if (!value || !dataType) return null;

  const unit = value.unit ?? fa.definition?.unit ?? "";

  switch (dataType) {
    case "number":
    case "integer":
    case "dimension": {
      if (value.value_number === null || value.value_number === undefined)
        return null;
      return unit
        ? `${value.value_number} ${unit}`
        : String(value.value_number);
    }
    case "text": {
      return value.value_text ?? null;
    }
    case "bool": {
      if (value.value_bool === null || value.value_bool === undefined)
        return null;
      return value.value_bool ? (
        <span aria-label="yes" className="text-emerald-600">
          {"✓"}
        </span>
      ) : (
        <span aria-label="no" className="text-rose-600">
          {"✗"}
        </span>
      );
    }
    case "enum": {
      const optId = value.value_enum_id;
      if (!optId) return null;
      const opt = fa.options?.find((o: AttributeOption) => o.id === optId);
      return opt?.label_en ?? optId;
    }
    case "range": {
      const min = value.value_min;
      const max = value.value_max;
      if (min === null && max === null) return null;
      const minStr = min === null || min === undefined ? "—" : String(min);
      const maxStr = max === null || max === undefined ? "—" : String(max);
      const range = `[${minStr}, ${maxStr}]`;
      return unit ? `${range} ${unit}` : range;
    }
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AttributeRow({
  fa,
  value,
}: {
  fa: FamilyAttribute;
  value: AttributeValue | undefined;
}) {
  const rendered = renderAttributeValue(fa, value);
  const missingRequired = fa.is_required && rendered === null;
  const label = fa.definition?.label_en ?? fa.attribute_id;

  return (
    <div className="flex flex-col gap-0.5 border-b py-2 last:border-b-0 sm:flex-row sm:items-center sm:gap-4">
      <dt className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground sm:w-44">
        <span>{label}</span>
        {fa.is_required ? (
          <Badge
            variant={missingRequired ? "destructive" : "secondary"}
            className="text-[10px]"
          >
            Required
          </Badge>
        ) : null}
      </dt>
      <dd className="text-sm font-medium">
        {rendered ?? <span className="text-muted-foreground">—</span>}
      </dd>
    </div>
  );
}

interface GroupedAttributes {
  groupCode: string;
  items: FamilyAttribute[];
}

function groupAttributes(template: FamilyAttribute[]): GroupedAttributes[] {
  const map = new Map<string, FamilyAttribute[]>();
  // Preserve insertion order so the backend `order_index` ordering (assumed
  // already applied server-side) is honoured.
  for (const fa of template) {
    const key = fa.group_code || "general";
    const bucket = map.get(key);
    if (bucket) bucket.push(fa);
    else map.set(key, [fa]);
  }
  return Array.from(map.entries()).map(([groupCode, items]) => ({
    groupCode,
    items,
  }));
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ProductSpecsCardEAV({
  sku,
  familyId,
}: ProductSpecsCardEAVProps) {
  const family = useFamilyAttributes(familyId ?? undefined);
  const values = useProductAttributes(sku);

  const valuesByAttrId = useMemo(() => {
    const m = new Map<string, AttributeValue>();
    for (const v of values.data ?? []) {
      m.set(v.attribute_id, v);
    }
    return m;
  }, [values.data]);

  const groups = useMemo(
    () => groupAttributes(family.data ?? []),
    [family.data],
  );

  if (!familyId) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Specs (Stage 2 — EAV)</CardTitle>
          <CardDescription>
            Family UUID is not assigned to this product yet — EAV view
            unavailable.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (family.isLoading || values.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64 w-full rounded-lg" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (family.isError || values.isError) {
    return (
      <p className="text-sm text-destructive">
        Could not load EAV attributes for this product.
      </p>
    );
  }

  if (groups.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Specs (Stage 2 — EAV)</CardTitle>
          <CardDescription>
            No attribute template configured for this family yet.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div
      className="grid gap-4 lg:grid-cols-2"
      data-testid="product-specs-eav-root"
    >
      {groups.map((group) => (
        <Card key={group.groupCode} data-testid={`group-${group.groupCode}`}>
          <CardHeader>
            <CardTitle>{humaniseGroupCode(group.groupCode)}</CardTitle>
            <CardDescription>Stage 2 — EAV</CardDescription>
          </CardHeader>
          <CardContent>
            <dl>
              {group.items.map((fa) => (
                <AttributeRow
                  key={fa.id}
                  fa={fa}
                  value={valuesByAttrId.get(fa.attribute_id)}
                />
              ))}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
