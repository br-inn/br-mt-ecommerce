import type { ReactNode } from "react";

export default function PricingDeskLayout({ children }: { children: ReactNode }) {
  return <div className="flex h-full flex-col bg-mt-bg">{children}</div>;
}
