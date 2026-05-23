"use client";

import * as React from "react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  type ScraperSourceRead,
  type ScraperSourceStatus,
} from "@/lib/api/endpoints/scraper-sources";
import { SourceDialog } from "./_source-dialog";

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

interface Props {
  source: ScraperSourceRead;
}

export function InfoTab({ source }: Props) {
  const t = useTranslations("admin.scraperSources.info");
  const tStatus = useTranslations("admin.scraperSources.status");
  const [editOpen, setEditOpen] = React.useState(false);

  return (
    <div className="space-y-4 max-w-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold">{source.name}</span>
          <Badge variant={STATUS_VARIANT[source.status]}>{tStatus(source.status)}</Badge>
        </div>
        <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
          {t("edit")}
        </Button>
      </div>

      <dl className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Slug</dt>
        <dd className="font-mono">{source.slug}</dd>

        <dt className="text-muted-foreground">{t("baseUrl")}</dt>
        <dd className="break-all">{source.base_url}</dd>

        <dt className="text-muted-foreground">{t("fetchMode")}</dt>
        <dd>{source.fetch_mode}</dd>

        <dt className="text-muted-foreground">{t("destinationProfile")}</dt>
        <dd>{source.destination_profile}</dd>

        {source.description && (
          <>
            <dt className="text-muted-foreground">{t("descriptionLabel")}</dt>
            <dd>{source.description}</dd>
          </>
        )}

        <dt className="text-muted-foreground">ID</dt>
        <dd className="font-mono text-xs text-muted-foreground">{source.id}</dd>
      </dl>

      <SourceDialog
        mode="edit"
        source={source}
        open={editOpen}
        onClose={() => setEditOpen(false)}
      />
    </div>
  );
}
