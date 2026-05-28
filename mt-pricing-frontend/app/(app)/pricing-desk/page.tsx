"use client";

import { useState } from "react";
import { PricingHeader } from "./_components/pricing-header";
import { Semaforo } from "./_components/semaforo";
import { FiltersBar } from "./_components/filters-bar";
import { CatalogTable } from "./_components/catalog-table";
import { ProposeButton } from "./_components/propose-button";
import { SidePanel } from "./_components/side-panel";
import { useCatalogSummary } from "@/lib/hooks/pricing-desk/use-catalog-summary";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

export default function PricingDeskPage() {
  const [channelCode, setChannelCode] = useState("amazon_uae");
  const [sellingModel, setSellingModel] = useState<SellingModel>("b2c");
  const [familyId, setFamilyId] = useState<string | undefined>();
  const [signal, setSignal] = useState<string | undefined>();
  const [selectedSkus, setSelectedSkus] = useState<Set<string>>(new Set());

  const toggleSku = (sku: string) => {
    setSelectedSkus((prev) => {
      const next = new Set(prev);
      if (next.has(sku)) next.delete(sku);
      else next.add(sku);
      return next;
    });
  };

  const toggleAll = (allCurrentlyShown: string[], selectAll: boolean) => {
    setSelectedSkus((prev) => {
      const next = new Set(prev);
      for (const s of allCurrentlyShown) {
        if (selectAll) next.add(s);
        else next.delete(s);
      }
      return next;
    });
  };

  const clearSelection = () => setSelectedSkus(new Set());

  const filters = {
    ...(familyId !== undefined && { familyId }),
    ...(signal !== undefined && { signal }),
  };

  const { data, isLoading, error } = useCatalogSummary(
    channelCode,
    sellingModel,
    filters,
  );

  return (
    <>
      <PricingHeader
        channelCode={channelCode}
        onChannelChange={(c) => {
          setChannelCode(c);
          setFamilyId(undefined);
          setSignal(undefined);
        }}
        sellingModel={sellingModel}
        onSellingModelChange={setSellingModel}
      />

      {data && <Semaforo summary={data.semaforo} />}

      <div className="flex flex-1 overflow-hidden">
        <SidePanel channelCode={channelCode} sellingModel={sellingModel} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <FiltersBar
            channelCode={channelCode}
            {...(familyId !== undefined && { familyId })}
            onFamilyChange={setFamilyId}
            {...(signal !== undefined && { signal })}
            onSignalChange={setSignal}
            totalShown={data?.rows.length ?? 0}
            totalAll={data?.semaforo.total ?? 0}
          />
          <ProposeButton
            channelCode={channelCode}
            sellingModel={sellingModel}
            selectedSkus={selectedSkus}
            onProposed={clearSelection}
          />

          <main className="flex-1 overflow-auto px-4 pb-6">
            {isLoading && (
              <p className="p-4 text-mt-ink-3">Cargando catálogo…</p>
            )}
            {error && (
              <p className="p-4 text-mt-danger">
                Error: {error instanceof Error ? error.message : "unknown"}
              </p>
            )}
            {data && (
              <CatalogTable
                channelCode={channelCode}
                sellingModel={sellingModel}
                rows={data.rows}
                selectedSkus={selectedSkus}
                onToggleSku={toggleSku}
                onToggleAll={toggleAll}
              />
            )}
          </main>
        </div>
      </div>
    </>
  );
}
