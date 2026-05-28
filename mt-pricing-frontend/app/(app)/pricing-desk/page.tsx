"use client";

import { useState } from "react";
import { PricingHeader } from "./_components/pricing-header";
import { useCatalogSummary } from "@/lib/hooks/pricing-desk/use-catalog-summary";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

export default function PricingDeskPage() {
  const [channelCode, setChannelCode] = useState("amazon_uae");
  const [sellingModel, setSellingModel] = useState<SellingModel>("b2c");

  const { data, isLoading, error } = useCatalogSummary(channelCode, sellingModel, {});

  return (
    <>
      <PricingHeader
        channelCode={channelCode}
        onChannelChange={setChannelCode}
        sellingModel={sellingModel}
        onSellingModelChange={setSellingModel}
      />
      <main className="flex-1 overflow-auto p-6">
        {isLoading && <p className="text-mt-ink-3">Cargando catálogo…</p>}
        {error && (
          <p className="text-mt-danger">
            Error: {error instanceof Error ? error.message : "unknown"}
          </p>
        )}
        {data && (
          <div className="rounded border bg-white p-4">
            <p className="text-sm">
              <strong>Catálogo:</strong> {data.semaforo.total} productos · Publicables:{" "}
              {data.semaforo.publishable} · Bloqueados: {data.semaforo.blocked} · En pérdida:{" "}
              {data.semaforo.in_loss}
            </p>
          </div>
        )}
      </main>
    </>
  );
}
