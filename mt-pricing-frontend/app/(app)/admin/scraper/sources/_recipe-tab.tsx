"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Plus, ChevronDown } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useScraperSourceRecipes,
  useCreateRecipe,
} from "@/lib/hooks/admin/use-scraper-sources";
import {
  type ScraperSourceRead,
  type RecipeRead,
  type ValidationStatus,
} from "@/lib/api/endpoints/scraper-sources";

const EMPTY_RECIPE = JSON.stringify(
  {
    url_templates: { search: "", pdp: "" },
    list_item_selector: "",
    fields: [{ name: "price", selector: ".price", type: "currency" }],
  },
  null,
  2,
);

const VALIDATION_VARIANT: Record<
  ValidationStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  unvalidated: "outline",
  passing: "default",
  failing: "destructive",
};

interface Props {
  source: ScraperSourceRead;
}

export function RecipeTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.recipe");
  const { data: recipes = [], isLoading } = useScraperSourceRecipes(source.id);
  const [dialogOpen, setDialogOpen] = React.useState(false);

  const liveRecipe = recipes.find((r) => r.is_live) ?? null;
  const previousRecipes = recipes.filter((r) => !r.is_live);

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">{t("active")}</div>;
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{t("active")}</span>
        <Button variant="outline" size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1.5 h-3.5 w-3.5" />
          {t("newVersion")}
        </Button>
      </div>

      {liveRecipe ? (
        <RecipeCard recipe={liveRecipe} />
      ) : (
        <p className="text-sm text-muted-foreground">{t("noRecipe")}</p>
      )}

      {previousRecipes.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
            <ChevronDown className="h-3.5 w-3.5" />
            {t("history")}
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {previousRecipes.map((r) => (
              <RecipeCard key={r.id} recipe={r} />
            ))}
          </CollapsibleContent>
        </Collapsible>
      )}

      <NewRecipeDialog
        source={source}
        liveRecipe={liveRecipe}
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
}

function RecipeCard({ recipe }: { recipe: RecipeRead }) {
  const t = useTranslations("admin.scraperSources.recipe");

  return (
    <div className="rounded-md border p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <span className="font-mono font-medium">
          {t("version", { version: String(recipe.version) })}
        </span>
        {recipe.is_live && <Badge className="text-xs">live</Badge>}
        <Badge
          variant={VALIDATION_VARIANT[recipe.validation_status as ValidationStatus]}
          className="text-xs"
        >
          {t(`validationStatus.${recipe.validation_status}`)}
        </Badge>
        <span className="text-xs text-muted-foreground ml-auto">
          {new Date(recipe.created_at).toLocaleDateString()}
        </span>
      </div>
      <pre className="rounded bg-muted p-3 text-xs overflow-x-auto max-h-48">
        {JSON.stringify(recipe.recipe, null, 2)}
      </pre>
    </div>
  );
}

function NewRecipeDialog({
  source,
  liveRecipe,
  open,
  onClose,
}: {
  source: ScraperSourceRead;
  liveRecipe: RecipeRead | null;
  open: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("admin.scraperSources.recipe");
  const createRecipe = useCreateRecipe(source.id);
  const [json, setJson] = React.useState("");
  const [jsonError, setJsonError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setJson(liveRecipe ? JSON.stringify(liveRecipe.recipe, null, 2) : EMPTY_RECIPE);
      setJsonError(null);
    }
  }, [open, liveRecipe]);

  const handleSave = async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      setJsonError(t("errorInvalidJson"));
      return;
    }
    setJsonError(null);
    try {
      await createRecipe.mutateAsync({ recipe: parsed as Record<string, unknown> });
      toast.success(t("saveSuccess"));
      onClose();
    } catch {
      toast.error(t("errorGeneric"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("newVersionTitle")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label>{t("recipeJson")}</Label>
          <p className="text-xs text-muted-foreground">{t("recipeJsonHint")}</p>
          <textarea
            value={json}
            onChange={(e) => setJson(e.target.value)}
            className="w-full rounded-md border bg-muted font-mono text-xs p-3 h-72 resize-y focus:outline-none focus:ring-1 focus:ring-ring"
            spellCheck={false}
          />
          {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={createRecipe.isPending}>
            {t("cancel")}
          </Button>
          <Button onClick={handleSave} disabled={createRecipe.isPending}>
            {createRecipe.isPending ? t("saving") : t("save")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
