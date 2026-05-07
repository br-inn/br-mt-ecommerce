"use client";

import { useTranslations } from "next-intl";
import { useQueryStates, parseAsString, parseAsStringEnum } from "nuqs";

import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FamilyFilter } from "@/components/domain/family-filter";
import type {
  DataQuality,
  ProductFamily,
  TranslationStatus,
} from "@/lib/api/endpoints/products";

const ANY = "__any";

const filterParsers = {
  family: parseAsString,
  data_quality: parseAsStringEnum<DataQuality>(["complete", "partial", "blocked"]),
  translation_status: parseAsStringEnum<TranslationStatus>(["draft", "pending", "approved"]),
  active: parseAsStringEnum<"all" | "active" | "inactive">(["all", "active", "inactive"]),
} as const;

export function useCatalogFilters() {
  const [state, setState] = useQueryStates(filterParsers, {
    history: "replace",
  });
  const activeBool: boolean | undefined =
    state.active === "active" ? true : state.active === "inactive" ? false : undefined;
  return {
    state,
    setState,
    asApi: {
      family: state.family ?? undefined,
      data_quality: state.data_quality ?? undefined,
      translation_status: state.translation_status ?? undefined,
      active: activeBool,
    },
  };
}

export function CatalogFilters() {
  const t = useTranslations("catalog.filters");
  const { state, setState } = useCatalogFilters();

  const reset = () =>
    setState({ family: null, data_quality: null, translation_status: null, active: null });

  return (
    <Card aria-label={t("title")}>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          {t("title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="filter-family">{t("family")}</Label>
          <FamilyFilter
            id="filter-family"
            value={(state.family ?? "") as ProductFamily | ""}
            onChange={(v) => setState({ family: v ?? null })}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-quality">{t("dataQuality")}</Label>
          <Select
            value={state.data_quality ?? ANY}
            onValueChange={(v) =>
              setState({ data_quality: v === ANY ? null : (v as DataQuality) })
            }
          >
            <SelectTrigger id="filter-quality">
              <SelectValue placeholder={t("anyQuality")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("anyQuality")}</SelectItem>
              <SelectItem value="complete">complete</SelectItem>
              <SelectItem value="partial">partial</SelectItem>
              <SelectItem value="blocked">blocked</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-translation">{t("translationStatus")}</Label>
          <Select
            value={state.translation_status ?? ANY}
            onValueChange={(v) =>
              setState({
                translation_status: v === ANY ? null : (v as TranslationStatus),
              })
            }
          >
            <SelectTrigger id="filter-translation">
              <SelectValue placeholder={t("anyTranslation")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>{t("anyTranslation")}</SelectItem>
              <SelectItem value="draft">draft</SelectItem>
              <SelectItem value="pending">pending</SelectItem>
              <SelectItem value="approved">approved</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="filter-active">{t("active")}</Label>
          <Select
            value={state.active ?? "all"}
            onValueChange={(v) =>
              setState({
                active: v === "all" ? null : (v as "active" | "inactive"),
              })
            }
          >
            <SelectTrigger id="filter-active">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("all")}</SelectItem>
              <SelectItem value="active">{t("active")}</SelectItem>
              <SelectItem value="inactive">{t("inactive")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button variant="ghost" size="sm" className="w-full" onClick={reset}>
          {t("clear")}
        </Button>
      </CardContent>
    </Card>
  );
}
