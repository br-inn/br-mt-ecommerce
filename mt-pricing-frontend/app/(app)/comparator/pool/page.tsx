"use client";

import * as React from "react";
import Link from "next/link";
import { parseAsString, parseAsStringEnum, useQueryState } from "nuqs";
import { DatabaseZap, ExternalLink, ImageIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { MT } from "@/components/mt/tokens";
import { Pill, MtButton } from "@/components/mt/primitives";
import { MtEmpty, MtError, MtSkeleton } from "@/components/mt/states";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import type {
  UnmatchedOfferMarketplace,
  UnmatchedOfferResponse,
  UnmatchedOfferStatus,
} from "@/lib/api/endpoints/unmatched-offers";
import {
  useUnmatchedOffers,
  useUnmatchedOffersStats,
} from "./_hooks/use-unmatched-offers";

// ---- Constants ---------------------------------------------------------------

const MARKETPLACE_VALUES = ["amazon_uae", "noon_uae"] as const;
const STATUS_VALUES = ["pending", "matched", "exhausted"] as const;

// ---- Helpers ----------------------------------------------------------------

function fmtScrapedAt(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 60) return `hace ${mins} min`;
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 24) return `hace ${hours} h`;
  const days = Math.floor(ms / 86_400_000);
  if (days === 1) return "hace 1 día";
  if (days < 30) return `hace ${days} días`;
  const months = Math.floor(days / 30);
  return `hace ${months} mes${months > 1 ? "es" : ""}`;
}

function fmtPrice(aed: string | null): string {
  if (!aed) return "—";
  const n = parseFloat(aed);
  if (isNaN(n)) return aed;
  return `AED ${n.toLocaleString("en-AE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Returns true if isLoading has been continuously true for longer than `ms`.
function useLoadingTimeout(isLoading: boolean, ms = 10_000): boolean {
  const [timedOut, setTimedOut] = React.useState(false);

  React.useEffect(() => {
    if (!isLoading) {
      setTimedOut(false);
      return;
    }
    const id = setTimeout(() => setTimedOut(true), ms);
    return () => clearTimeout(id);
  }, [isLoading, ms]);

  return timedOut;
}

// ---- Sub-components ---------------------------------------------------------

function StatCard({
  label,
  value,
  loading,
}: {
  label: string;
  value: number | undefined;
  loading: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-1 rounded-md border p-4"
      style={{ background: MT.surface, borderColor: MT.border }}
    >
      <span className="text-[11px] uppercase tracking-[0.5px]" style={{ color: MT.ink4 }}>
        {label}
      </span>
      {loading ? (
        <MtSkeleton width={56} height={24} />
      ) : (
        <span className="text-[22px] font-semibold leading-none" style={{ color: MT.ink }}>
          {(value ?? 0).toLocaleString("es-AE")}
        </span>
      )}
    </div>
  );
}

function MarketplaceBadge({ mp }: { mp: UnmatchedOfferMarketplace }) {
  if (mp === "amazon_uae") {
    return (
      <span
        className="inline-flex h-5 items-center whitespace-nowrap rounded-[4px] border px-1.5 text-[11px] font-medium leading-none"
        style={{
          background: "#fff7ed",
          color: "#c2410c",
          borderColor: "#fed7aa",
        }}
      >
        Amazon UAE
      </span>
    );
  }
  return (
    <span
      className="inline-flex h-5 items-center whitespace-nowrap rounded-[4px] border px-1.5 text-[11px] font-medium leading-none"
      style={{
        background: "#eff6ff",
        color: "#1d4ed8",
        borderColor: "#bfdbfe",
      }}
    >
      Noon UAE
    </span>
  );
}

function StatusBadge({ status }: { status: UnmatchedOfferStatus }) {
  if (status === "pending") {
    return (
      <Pill tone="warning" dot>
        Pendiente
      </Pill>
    );
  }
  if (status === "matched") {
    return (
      <Pill tone="success" dot>
        Matched
      </Pill>
    );
  }
  return (
    <Pill tone="danger" dot>
      Agotada
    </Pill>
  );
}

function AttemptsBadge({ attempts }: { attempts: number }) {
  const tone = attempts >= 3 ? "danger" : attempts > 0 ? "warning" : "neutral";
  return (
    <Pill tone={tone} mono>
      {attempts}
    </Pill>
  );
}

function OfferThumbnail({ url }: { url: string | null }) {
  if (!url) {
    return (
      <div
        className="flex size-10 shrink-0 items-center justify-center rounded"
        style={{ background: MT.surface3 }}
      >
        <ImageIcon className="size-4" style={{ color: MT.ink4 }} />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt=""
      className="size-10 shrink-0 rounded object-cover"
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.display = "none";
      }}
    />
  );
}

function SpecTag({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-baseline gap-1">
      <span className="text-[10px] uppercase tracking-[0.3px]" style={{ color: MT.ink4 }}>
        {label}
      </span>
      <span
        className="rounded px-1 py-0.5 text-[10.5px] font-medium"
        style={{ background: MT.surface3, color: MT.ink2, border: `1px solid ${MT.border}` }}
      >
        {value}
      </span>
    </span>
  );
}

function SpecsCell({ specs }: { specs: Record<string, unknown> }) {
  const str = (v: unknown) => (v !== null && v !== undefined ? String(v) : null);

  const type = str(specs.valve_type ?? specs.type);
  const material = str(specs.material);
  const size = str(specs.size);
  const pn = str(specs.pn);
  const thread = str(specs.thread ?? specs.end_connection);
  const ways = str(specs.ways);
  const alloy = str(specs.alloy);
  const mpn = str(specs.mpn ?? specs.part_number);

  const hasAny = [type, material, size, pn, thread, ways, alloy, mpn].some(Boolean);

  if (!hasAny) {
    return <span className="text-[11px]" style={{ color: MT.ink4 }}>—</span>;
  }

  return (
    <div className="flex flex-col gap-1">
      {type && <SpecTag label="Tipo" value={type} />}
      {material && <SpecTag label="Mat." value={material} />}
      {size && <SpecTag label="DN" value={`${size}"`} />}
      {pn && <SpecTag label="PN" value={`PN${pn}`} />}
      {thread && <SpecTag label="Rosca" value={thread} />}
      {ways && <SpecTag label="Vías" value={ways} />}
      {alloy && <SpecTag label="Aleación" value={alloy} />}
      {mpn && <SpecTag label="MPN" value={mpn} />}
    </div>
  );
}

// ---- Table row ---------------------------------------------------------------

function OfferRow({ item, even }: { item: UnmatchedOfferResponse; even: boolean }) {
  return (
    <tr style={{ background: even ? MT.surface : MT.surface2 }}>
      {/* Thumbnail */}
      <td className="px-3 py-2 align-top">
        <OfferThumbnail url={item.image_url} />
      </td>

      {/* Title + URL */}
      <td className="px-3 py-2 align-top" style={{ maxWidth: 280 }}>
        <div className="flex items-start gap-1.5">
          <span
            className="line-clamp-3 text-[12.5px] leading-snug"
            style={{ color: MT.ink }}
          >
            {item.source_url ? (
              <a
                href={item.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
                style={{ color: MT.brand }}
              >
                {item.title}
              </a>
            ) : (
              item.title
            )}
          </span>
          {item.source_url ? (
            <a
              href={item.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-0.5 shrink-0"
              aria-label="Abrir en marketplace"
            >
              <ExternalLink className="size-3" style={{ color: MT.ink4 }} />
            </a>
          ) : null}
        </div>
        {/* Brand inline under title */}
        {item.brand && (
          <span className="mt-0.5 block text-[11px]" style={{ color: MT.ink4 }}>
            {item.brand}
          </span>
        )}
      </td>

      {/* Technical specs */}
      <td className="px-3 py-2 align-top">
        <SpecsCell specs={item.specs_jsonb} />
      </td>

      {/* Marketplace */}
      <td className="px-3 py-2 align-top">
        <MarketplaceBadge mp={item.marketplace} />
      </td>

      {/* Price */}
      <td className="px-3 py-2 align-top text-right">
        <span className="mt-mono text-[12px] font-medium" style={{ color: MT.ink2 }}>
          {fmtPrice(item.price_aed)}
        </span>
      </td>

      {/* Source SKU */}
      <td className="px-3 py-2 align-top">
        {item.source_sku ? (
          <span className="mt-mono text-[11px]" style={{ color: MT.ink4 }}>
            {item.source_sku}
          </span>
        ) : (
          <span style={{ color: MT.ink4 }}>—</span>
        )}
      </td>

      {/* Attempts */}
      <td className="px-3 py-2 align-top text-center">
        <AttemptsBadge attempts={item.match_attempts} />
      </td>

      {/* Status */}
      <td className="px-3 py-2 align-top">
        <StatusBadge status={item.status} />
      </td>

      {/* Scraped at */}
      <td className="px-3 py-2 align-top text-[11px]" style={{ color: MT.ink3 }}>
        {fmtScrapedAt(item.scraped_at)}
      </td>
    </tr>
  );
}

// ---- Main page ---------------------------------------------------------------

export default function UnmatchedOffersPoolPage() {
  const t = useTranslations("comparator.pool");

  // Filters in URL state
  const [marketplace, setMarketplace] = useQueryState(
    "marketplace",
    parseAsStringEnum<UnmatchedOfferMarketplace>([...MARKETPLACE_VALUES]),
  );
  const [status, setStatus] = useQueryState(
    "status",
    parseAsStringEnum<UnmatchedOfferStatus>([...STATUS_VALUES]),
  );
  const [searchInput, setSearchInput] = useQueryState("q", parseAsString.withDefault(""));

  const debouncedSearch = useDebouncedValue(searchInput, 300);

  const isFilterActive = Boolean(marketplace ?? status ?? debouncedSearch);

  const filters = React.useMemo(
    () => ({
      ...(marketplace ? { marketplace } : {}),
      ...(status ? { status } : {}),
      ...(debouncedSearch ? { q: debouncedSearch } : {}),
    }),
    [marketplace, status, debouncedSearch],
  );

  const {
    data,
    isLoading,
    isError,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useUnmatchedOffers(filters);

  const { data: stats, isLoading: statsLoading } = useUnmatchedOffersStats();

  const listTimedOut = useLoadingTimeout(isLoading);
  const statsTimedOut = useLoadingTimeout(statsLoading);

  const items: UnmatchedOfferResponse[] = React.useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );
  const total = data?.pages[0]?.total ?? null;

  const showListError = isError || listTimedOut;
  const showStatsLoading = statsLoading && !statsTimedOut;

  function clearFilters() {
    void setMarketplace(null);
    void setStatus(null);
    void setSearchInput("");
  }

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      {/* Page header */}
      <div
        className="flex items-center justify-between border-b bg-mt-surface px-6 py-3.5"
        style={{ borderColor: MT.border }}
      >
        <div className="flex items-center gap-2">
          <DatabaseZap className="size-4 shrink-0" style={{ color: MT.brand }} />
          <span
            className="text-[15px] font-semibold tracking-[-0.1px]"
            style={{ color: MT.ink }}
          >
            Pool scrapeado
          </span>
          <span className="mt-mono ml-2 text-xs" style={{ color: MT.ink4 }}>
            {total !== null
              ? `${total.toLocaleString()} ofertas`
              : items.length > 0
                ? `${items.length} cargadas`
                : null}
          </span>
        </div>
      </div>

      {/* Stat cards */}
      <div
        className="grid grid-cols-2 gap-3 border-b bg-mt-surface px-6 py-4 md:grid-cols-4"
        style={{ borderColor: MT.border }}
      >
        <StatCard
          label="Pendientes"
          value={stats?.total_pending}
          loading={showStatsLoading}
        />
        <StatCard
          label="Matched hoy"
          value={stats?.matched_last_24h}
          loading={showStatsLoading}
        />
        <StatCard
          label="Agotadas"
          value={stats?.total_exhausted}
          loading={showStatsLoading}
        />
        <StatCard
          label="Últimos 7 días"
          value={stats?.scraped_last_7d}
          loading={showStatsLoading}
        />
      </div>

      {/* Filter bar */}
      <div
        className="flex flex-wrap items-center gap-2 border-b bg-mt-surface px-6 py-2.5"
        style={{ borderColor: MT.border }}
      >
        {/* Marketplace selector */}
        <div className="flex items-center gap-1 text-[12.5px]" style={{ color: MT.ink3 }}>
          <span className="mr-1 text-[11px] uppercase tracking-[0.4px]" style={{ color: MT.ink4 }}>
            Marketplace
          </span>
          {([null, "amazon_uae", "noon_uae"] as const).map((mp) => {
            const label =
              mp === null ? "Todos" : mp === "amazon_uae" ? "Amazon UAE" : "Noon UAE";
            const selected = marketplace === mp;
            return (
              <button
                key={label}
                type="button"
                onClick={() => void setMarketplace(mp)}
                className="rounded-md px-2.5 py-1 text-[12.5px] transition-colors"
                style={{
                  background: selected ? MT.brandSoft : "transparent",
                  color: selected ? MT.brandDeep : MT.ink3,
                  fontWeight: selected ? 600 : 400,
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div
          className="mx-1 h-4 w-px"
          style={{ background: MT.border }}
          aria-hidden
        />

        {/* Status selector */}
        <div className="flex items-center gap-1">
          <span className="mr-1 text-[11px] uppercase tracking-[0.4px]" style={{ color: MT.ink4 }}>
            Estado
          </span>
          {(
            [null, "pending", "matched", "exhausted"] as const
          ).map((s) => {
            const label =
              s === null
                ? "Todos"
                : s === "pending"
                  ? "Pendientes"
                  : s === "matched"
                    ? "Matched"
                    : "Agotadas";
            const selected = status === s;
            return (
              <button
                key={label}
                type="button"
                onClick={() => void setStatus(s)}
                className="rounded-md px-2.5 py-1 text-[12.5px] transition-colors"
                style={{
                  background: selected ? MT.brandSoft : "transparent",
                  color: selected ? MT.brandDeep : MT.ink3,
                  fontWeight: selected ? 600 : 400,
                }}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div
          className="mx-1 h-4 w-px"
          style={{ background: MT.border }}
          aria-hidden
        />

        {/* Search */}
        <input
          type="search"
          value={searchInput}
          onChange={(e) => void setSearchInput(e.target.value)}
          placeholder="Buscar por título…"
          className="h-7 min-w-[200px] rounded-md border px-3 text-[12.5px] outline-none focus:ring-1 focus:ring-offset-0"
          style={{
            borderColor: MT.border,
            background: MT.surface,
            color: MT.ink,
          }}
        />
      </div>

      {/* Error */}
      {showListError ? (
        <div className="px-6 py-3">
          <MtError
            message={t("loadError")}
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      {/* Table */}
      <div className="mt-thin-scroll flex-1 overflow-auto bg-mt-surface">
        <table className="w-full border-collapse text-[12.5px]">
          <thead
            className="sticky top-0 z-10"
            style={{ background: MT.surface2, borderBottom: `1px solid ${MT.border}` }}
          >
            <tr>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 48 }}
              >
                Img
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, minWidth: 220 }}
              >
                Título / Marca
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, minWidth: 160 }}
              >
                Specs técnicos
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 110 }}
              >
                Marketplace
              </th>
              <th
                className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 120 }}
              >
                Precio
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 100 }}
              >
                SKU origen
              </th>
              <th
                className="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 72 }}
              >
                Intentos
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 100 }}
              >
                Estado
              </th>
              <th
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.5px]"
                style={{ color: MT.ink4, width: 100 }}
              >
                Scrapeado
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && !listTimedOut
              ? Array.from({ length: 12 }).map((_, i) => (
                  <tr key={`sk-${i}`} style={{ background: i % 2 ? MT.surface : MT.surface2 }}>
                    {Array.from({ length: 9 }).map((__, j) => (
                      <td key={j} className="px-3 py-2">
                        <MtSkeleton width={j === 1 ? 200 : j === 0 ? 40 : 70} height={j === 0 ? 40 : 16} />
                      </td>
                    ))}
                  </tr>
                ))
              : items.map((item, i) => (
                  <OfferRow key={item.id} item={item} even={i % 2 === 0} />
                ))}
          </tbody>
        </table>

        {/* Empty states — only shown when not loading and no error */}
        {!isLoading && !showListError && items.length === 0 ? (
          isFilterActive ? (
            <MtEmpty
              title={t("filteredEmptyTitle")}
              hint={t("filteredEmptyHint")}
              icon={<DatabaseZap className="size-6" strokeWidth={1.4} />}
              cta={
                <MtButton size="sm" tone="neutral" onClick={clearFilters}>
                  {t("filteredEmptyCta")}
                </MtButton>
              }
            />
          ) : (
            <MtEmpty
              title={t("emptyTitle")}
              hint={t("emptyHint")}
              icon={<DatabaseZap className="size-6" strokeWidth={1.4} />}
              cta={
                <Link href="/admin/scraper">
                  <MtButton size="sm" tone="primary">
                    {t("emptyCta")}
                  </MtButton>
                </Link>
              }
            />
          )
        ) : null}
      </div>

      {/* Cargar más footer */}
      {items.length > 0 || (isLoading && !listTimedOut) ? (
        <div
          className="flex items-center justify-between border-t bg-mt-surface px-6 py-2.5"
          style={{ borderColor: MT.border }}
        >
          <span className="text-[11.5px]" style={{ color: MT.ink4 }}>
            {items.length} oferta{items.length !== 1 ? "s" : ""} cargada
            {items.length !== 1 ? "s" : ""}
            {total !== null ? ` de ${total.toLocaleString()}` : ""}
          </span>
          {hasNextPage ? (
            <button
              type="button"
              className="rounded-md px-3 py-1.5 text-[12.5px] transition-colors hover:bg-mt-surface-2 disabled:opacity-50"
              style={{
                border: `1px solid ${MT.border}`,
                background: MT.surface,
                color: MT.ink2,
              }}
              disabled={isFetchingNextPage}
              onClick={() => void fetchNextPage()}
            >
              {isFetchingNextPage ? "Cargando…" : "Cargar más"}
            </button>
          ) : items.length > 0 ? (
            <span className="text-[11.5px]" style={{ color: MT.ink4 }}>
              Fin de resultados
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
