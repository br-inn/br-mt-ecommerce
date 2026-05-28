"use client";

import { CostParamsSection } from "./cost-params-section";
import { FamilyMarginsSection } from "./family-margins-section";
import { ImportExcelSection } from "./import-excel-section";
import { OptimizeSection } from "./optimize-section";
import { ScenariosSection } from "./scenarios-section";
import type { SellingModel } from "@/lib/api/endpoints/pricing-desk";

interface Props {
  channelCode: string;
  sellingModel: SellingModel;
}

export function SidePanel({ channelCode, sellingModel }: Props) {
  return (
    <aside className="mt-thin-scroll sticky top-0 flex h-[calc(100vh-3.5rem)] w-[320px] flex-col overflow-y-auto border-r border-mt-border bg-white">
      <CostParamsSection channelCode={channelCode} />
      <FamilyMarginsSection
        channelCode={channelCode}
        sellingModel={sellingModel}
      />
      <OptimizeSection channelCode={channelCode} sellingModel={sellingModel} />
      <ScenariosSection channelCode={channelCode} sellingModel={sellingModel} />
      <ImportExcelSection channelCode={channelCode} />
    </aside>
  );
}
