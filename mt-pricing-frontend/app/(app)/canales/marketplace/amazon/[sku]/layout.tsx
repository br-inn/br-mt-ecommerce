import type { ReactNode } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { AmazonHeader } from "./_components/amazon-header";
import { AmazonTabs } from "./_components/amazon-tabs";

interface LayoutProps {
  children: ReactNode;
  params: Promise<{ sku: string }>;
}

export default async function AmazonListingLayout({ children, params }: LayoutProps) {
  const { sku } = await params;

  return (
    <div className="mx-auto max-w-screen-xl space-y-6 px-6 py-6">
      {/* Breadcrumb */}
      <nav aria-label="Miga de pan" className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href="/canales/marketplace/amazon" className="hover:text-foreground transition-colors">
          Amazon UAE
        </Link>
        <ChevronRight className="h-3.5 w-3.5 shrink-0" />
        <span className="font-mono text-foreground">{sku}</span>
      </nav>

      <AmazonHeader sku={sku} />
      <AmazonTabs sku={sku} />
      <div>{children}</div>
    </div>
  );
}
