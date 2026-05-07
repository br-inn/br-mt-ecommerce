import { getTranslations } from "next-intl/server";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AuditTimeline } from "@/components/domain/audit-timeline";

interface PageProps {
  params: Promise<{ sku: string }>;
}

export default async function ProductAuditPage({ params }: PageProps) {
  const { sku } = await params;
  const t = await getTranslations("catalog.audit");
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {t("title")} — <span className="font-mono">{sku}</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <AuditTimeline entityType="product" entityId={sku} />
      </CardContent>
    </Card>
  );
}
