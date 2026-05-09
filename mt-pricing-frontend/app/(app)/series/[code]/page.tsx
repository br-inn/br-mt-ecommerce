import { SeriesLanding } from "./_client";

export const dynamic = "force-dynamic";

export default async function SeriesLandingPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return <SeriesLanding code={code} />;
}
