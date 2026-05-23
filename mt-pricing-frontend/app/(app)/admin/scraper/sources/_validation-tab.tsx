"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useScraperSourceRecipes,
  useValidateRecipe,
  useActivateSource,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  type ScraperSourceRead,
  type ValidateResponse,
} from "@/lib/api/endpoints/scraper-sources";

interface Props {
  source: ScraperSourceRead;
}

export function ValidationTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.validation");
  const { data: recipes = [] } = useScraperSourceRecipes(source.id);
  const validate = useValidateRecipe(source.id);
  const activate = useActivateSource(source.id);

  const [testUrl, setTestUrl] = React.useState("");
  const [selectedRecipeId, setRecipeId] = React.useState<string>("");
  const [result, setResult] = React.useState<ValidateResponse | null>(null);

  // Derive effective recipe: user selection → live recipe → first recipe
  const recipeId =
    selectedRecipeId ||
    recipes.find((r) => r.is_live)?.id ||
    recipes[0]?.id ||
    "";

  const handleValidate = async () => {
    if (!testUrl || !recipeId) return;
    setResult(null);
    try {
      const res = await validate.mutateAsync({ recipe_id: recipeId, test_url: testUrl });
      setResult(res);
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  const handleActivate = async () => {
    if (!recipeId) return;
    try {
      await activate.mutateAsync({ recipe_id: recipeId });
      toast.success(t("activateSuccess"));
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  const allPassing =
    result !== null && Object.values(result.field_results).every((v) => v === "pass");

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="grid grid-cols-[1fr_auto] gap-3 items-end">
        <div className="space-y-1.5">
          <Label htmlFor="val-url">{t("testUrl")}</Label>
          <Input
            id="val-url"
            value={testUrl}
            onChange={(e) => setTestUrl(e.target.value)}
            placeholder={t("testUrlPlaceholder")}
          />
        </div>
        <Button onClick={handleValidate} disabled={!testUrl || !recipeId || validate.isPending}>
          {validate.isPending ? t("running") : t("run")}
        </Button>
      </div>

      {recipes.length > 0 && (
        <div className="space-y-1.5">
          <Label htmlFor="val-recipe">{t("recipe")}</Label>
          <Select value={recipeId} onValueChange={setRecipeId}>
            <SelectTrigger id="val-recipe" className="w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {recipes.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  v{r.version}
                  {r.is_live ? " (live)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">{t("results")}</span>
            <Badge variant={allPassing ? "default" : "destructive"}>{result.status}</Badge>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("fieldName")}</TableHead>
                <TableHead>{t("fieldResult")}</TableHead>
                <TableHead>{t("fieldValue")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(result.field_results).map(([field, res]) => (
                <TableRow key={field}>
                  <TableCell className="font-mono text-xs">{field}</TableCell>
                  <TableCell>
                    {res === "pass" ? (
                      <span className="flex items-center gap-1 text-green-600 text-xs">
                        <CheckCircle2 className="h-3.5 w-3.5" /> {t("pass")}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-destructive text-xs">
                        <XCircle className="h-3.5 w-3.5" /> {res}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {result.records[0]?.[field] != null ? String(result.records[0][field]) : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center gap-3">
            <Button
              onClick={handleActivate}
              disabled={!allPassing || activate.isPending}
              variant={allPassing ? "default" : "outline"}
            >
              {activate.isPending ? t("activating") : t("activate")}
            </Button>
            {!allPassing && (
              <p className="text-xs text-muted-foreground">{t("activateBlocked")}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
