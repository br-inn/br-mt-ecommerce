"use client";

import { useTranslations } from "next-intl";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PRODUCT_FAMILIES, type ProductFamily } from "@/lib/api/endpoints/products";

interface Props {
  value: ProductFamily | "" | undefined;
  onChange: (value: ProductFamily | undefined) => void;
  id?: string;
}

const ANY = "__any";

/**
 * Combobox de familias. Por ahora la lista es estática (constantes
 * `PRODUCT_FAMILIES`); cuando exista el endpoint `GET /catalog/families`,
 * cambiamos a `useQuery`. TODO Sprint 2.
 */
export function FamilyFilter({ value, onChange, id }: Props) {
  const t = useTranslations("catalog.filters");
  const current = value && value.length > 0 ? value : ANY;
  return (
    <Select
      value={current}
      onValueChange={(v) => onChange(v === ANY ? undefined : (v as ProductFamily))}
    >
      <SelectTrigger id={id} aria-label={t("family")}>
        <SelectValue placeholder={t("anyFamily")} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ANY}>{t("anyFamily")}</SelectItem>
        {PRODUCT_FAMILIES.map((family) => (
          <SelectItem key={family} value={family} className="capitalize">
            {family}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
