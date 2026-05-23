"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils/cn";
import { useScraperSources } from "@/lib/hooks/admin/use-scraper-sources";
import {
  type ScraperSourceRead,
  type ScraperSourceStatus,
} from "@/lib/api/endpoints/scraper-sources";

import { SourceDialog } from "./_source-dialog";
import { InfoTab } from "./_info-tab";
import { RecipeTab } from "./_recipe-tab";
import { ValidationTab } from "./_validation-tab";

const STATUS_VARIANT: Record<
  ScraperSourceStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  draft: "outline",
  testing: "secondary",
  active: "default",
  disabled: "destructive",
  degraded: "destructive",
};

export function ScraperSourcesClient() {
  const t = useTranslations("admin.scraperSources");
  const tStatus = useTranslations("admin.scraperSources.status");
  const { data: sources = [], isLoading } = useScraperSources();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  const selected = sources.find((s) => s.id === selectedId) ?? null;

  return (
    <div className="flex gap-4 h-[calc(100vh-220px)] min-h-[500px]">
      {/* Left panel — source list */}
      <div className="w-64 flex-shrink-0 flex flex-col gap-3">
        <Button size="sm" className="w-full" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          {t("newSource")}
        </Button>

        <div className="flex-1 overflow-y-auto rounded-md border divide-y">
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between p-3">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-5 w-14" />
                </div>
              ))
            : sources.map((source) => (
                <button
                  key={source.id}
                  onClick={() => setSelectedId(source.id)}
                  className={cn(
                    "w-full flex items-center justify-between p-3 text-left text-sm hover:bg-muted/50 transition-colors",
                    selectedId === source.id && "bg-muted font-medium",
                  )}
                >
                  <span className="truncate max-w-[120px]" title={source.name}>
                    {source.name}
                  </span>
                  <Badge
                    variant={STATUS_VARIANT[source.status]}
                    className="ml-2 shrink-0 text-xs"
                  >
                    {tStatus(source.status)}
                  </Badge>
                </button>
              ))}
        </div>
      </div>

      {/* Right panel — detail */}
      <div className="flex-1 min-w-0">
        {selected ? (
          <SourceDetail source={selected} />
        ) : (
          <div className="h-full flex items-center justify-center text-sm text-muted-foreground border rounded-md">
            {t("selectSource")}
          </div>
        )}
      </div>

      <SourceDialog
        mode="create"
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={(s) => setSelectedId(s.id)}
      />
    </div>
  );
}

function SourceDetail({ source }: { source: ScraperSourceRead }) {
  const t = useTranslations("admin.scraperSources.tabs");

  return (
    <Tabs defaultValue="info" className="h-full flex flex-col">
      <TabsList className="w-fit">
        <TabsTrigger value="info">{t("info")}</TabsTrigger>
        <TabsTrigger value="recipe">{t("recipe")}</TabsTrigger>
        <TabsTrigger value="validation">{t("validation")}</TabsTrigger>
      </TabsList>
      <div className="flex-1 overflow-y-auto mt-4">
        <TabsContent value="info" className="mt-0">
          <InfoTab source={source} />
        </TabsContent>
        <TabsContent value="recipe" className="mt-0">
          <RecipeTab source={source} />
        </TabsContent>
        <TabsContent value="validation" className="mt-0">
          <ValidationTab source={source} />
        </TabsContent>
      </div>
    </Tabs>
  );
}
