"use client";

import * as React from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ChevronDown, ChevronRight, UploadCloud } from "lucide-react";

import {
  CostCoverageCard,
  MissingSkusTable,
} from "@/components/domain/costs/cost-coverage-card";
import { MtButton, SectionCard } from "@/components/mt/primitives";
import { MtError, MtSkeleton } from "@/components/mt/states";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDashboardStats } from "@/lib/hooks/use-dashboard";
import { useCostDashboardOverview } from "@/lib/hooks/admin/use-cost-dashboard";
import { type SchemeCoverage } from "@/lib/api/endpoints/cost-dashboard";

import { CostosTable } from "./_components/costos-table";
import { CostosToolbar } from "./_components/costos-toolbar";

/**
 * `/costos` como módulo de primer nivel: tres pestañas.
 *  - Resumen: dashboard de cobertura por esquema (`CostCoverageOverview`).
 *  - Costes: listado global filtrable (`CostosToolbar` + `CostosTable`).
 *  - Importar: panel que enlaza al importer batch (`/imports/costs`).
 */
export function CostDashboardClient() {
  const t = useTranslations("costos");

  return (
    <Tabs defaultValue="resumen" className="space-y-4">
      <TabsList>
        <TabsTrigger value="resumen" data-testid="costos-tab-resumen">
          {t("tabs.resumen")}
        </TabsTrigger>
        <TabsTrigger value="costes" data-testid="costos-tab-costes">
          {t("tabs.costes")}
        </TabsTrigger>
        <TabsTrigger value="importar" data-testid="costos-tab-importar">
          {t("tabs.importar")}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="resumen">
        <CostCoverageOverview />
      </TabsContent>

      <TabsContent value="costes" className="space-y-4">
        <CostosToolbar />
        <CostosTable />
      </TabsContent>

      <TabsContent value="importar">
        <ImportarPanel />
      </TabsContent>
    </Tabs>
  );
}

/** Tab "Importar": enlaza al wizard de importación batch existente. */
function ImportarPanel() {
  const t = useTranslations("costos.importar");
  return (
    <SectionCard title={t("title")}>
      <div className="space-y-4 p-4 text-sm text-muted-foreground">
        <p>{t("description")}</p>
        <MtButton tone="primary" icon={<UploadCloud className="size-3.5" />} asChild>
          <Link href="/imports/costs" data-testid="costos-import-link">
            {t("cta")}
          </Link>
        </MtButton>
      </div>
    </SectionCard>
  );
}

/** Tab "Resumen": dashboard de cobertura por esquema (contenido original). */
function CostCoverageOverview() {
  const t = useTranslations("costsDashboard");

  const stats = useDashboardStats();
  const totalProducts = stats.data?.catalog.products_total ?? 0;
  const overview = useCostDashboardOverview(totalProducts, !!stats.data);

  const [expanded, setExpanded] = React.useState<string | null>(null);

  if (stats.isLoading || (overview.isLoading && !overview.data)) {
    return (
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <MtSkeleton key={i} height={110} className="w-full" />
          ))}
        </div>
        <MtSkeleton height={200} className="w-full" />
      </div>
    );
  }

  if (stats.isError) {
    return (
      <MtError
        message={t("errors.statsLoadFailed")}
        onRetry={() => void stats.refetch()}
      />
    );
  }
  if (overview.isError) {
    return (
      <MtError
        message={t("errors.overviewLoadFailed")}
        onRetry={() => void overview.refetch()}
      />
    );
  }
  if (!overview.data) {
    return (
      <MtError
        message={t("errors.overviewLoadFailed")}
        onRetry={() => void overview.refetch()}
      />
    );
  }

  const data = overview.data;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {data.schemes.map((cov) => (
          <CostCoverageCard
            key={cov.scheme}
            coverage={cov}
            totalProducts={totalProducts}
          />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("schemesDetailTitle")}</CardTitle>
          <CardDescription>
            {t("schemesDetailSubtitle", {
              total: totalProducts,
              computedAt: new Date(data.computedAt).toLocaleString(),
            })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {data.schemes.map((cov) => (
            <SchemeRow
              key={cov.scheme}
              coverage={cov}
              totalProducts={totalProducts}
              expanded={expanded === cov.scheme}
              onToggle={() =>
                setExpanded(expanded === cov.scheme ? null : cov.scheme)
              }
            />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

interface SchemeRowProps {
  coverage: SchemeCoverage;
  totalProducts: number;
  expanded: boolean;
  onToggle: () => void;
}

function SchemeRow({
  coverage,
  totalProducts,
  expanded,
  onToggle,
}: SchemeRowProps) {
  const t = useTranslations("costsDashboard");
  const covered = Math.max(0, totalProducts - coverage.missingCount);
  const pct =
    totalProducts > 0 ? Math.round((covered / totalProducts) * 100) : 0;

  return (
    <div className="overflow-hidden rounded-md border">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 bg-muted/30 px-4 py-3 text-left transition-colors hover:bg-muted/60"
        aria-expanded={expanded}
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0" />
        )}
        <span className="flex-1 font-mono text-sm font-semibold">
          {coverage.scheme}
        </span>
        <span className="text-xs text-muted-foreground">
          {t("coveredOfTotal", { covered, total: totalProducts })}
        </span>
        <span className="font-mono text-sm font-semibold tabular-nums">
          {pct}%
        </span>
      </button>
      {expanded ? (
        <div className="p-3">
          <MissingSkusTable coverage={coverage} />
        </div>
      ) : null}
    </div>
  );
}
