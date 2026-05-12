"use client";

import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProductPressureTemperature } from "@/lib/hooks/use-dimensions";
import type { PressureTemperaturePoint } from "@/lib/api/types-dimensions";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PressureTemperatureChartProps {
  sku: string;
  seriesVariantCode?: string;
  /** Override default chart size — useful for tests. */
  width?: number;
  height?: number;
}

// ---------------------------------------------------------------------------
// Layout constants
// ---------------------------------------------------------------------------

const DEFAULT_WIDTH = 640;
const DEFAULT_HEIGHT = 320;
const MARGIN = { top: 16, right: 16, bottom: 40, left: 56 };

const SERIES_COLOURS = [
  "#2563eb", // blue-600
  "#dc2626", // red-600
  "#16a34a", // green-600
  "#ea580c", // orange-600
  "#7c3aed", // violet-600
  "#0891b2", // cyan-600
];

// ---------------------------------------------------------------------------
// Helpers (exported for unit tests)
// ---------------------------------------------------------------------------

/**
 * Group a flat list of P-T points by their `series_variant_code`. Points
 * with no variant land in the bucket keyed by the empty string. Each
 * bucket is sorted by ascending `temperature_c` so the resulting polyline
 * is monotone in X.
 */
export function groupBySeries(
  points: PressureTemperaturePoint[],
): Map<string, PressureTemperaturePoint[]> {
  const out = new Map<string, PressureTemperaturePoint[]>();
  for (const p of points) {
    const key = p.series_variant_code ?? "";
    if (!out.has(key)) out.set(key, []);
    out.get(key)!.push(p);
  }
  for (const [k, arr] of out) {
    arr.sort((a, b) => Number(a.temperature_c) - Number(b.temperature_c));
    out.set(k, arr);
  }
  return out;
}

/**
 * Compute axis ranges from all points. Pads each dimension by 10% so the
 * outermost markers are not flush against the chart border. Returns null
 * when there are no points.
 */
export function computeRanges(points: PressureTemperaturePoint[]): {
  minT: number;
  maxT: number;
  minP: number;
  maxP: number;
} | null {
  if (points.length === 0) return null;
  let minT = Number.POSITIVE_INFINITY;
  let maxT = Number.NEGATIVE_INFINITY;
  let minP = Number.POSITIVE_INFINITY;
  let maxP = Number.NEGATIVE_INFINITY;
  for (const p of points) {
    const t = Number(p.temperature_c);
    const pr = Number(p.pressure_max_bar);
    if (t < minT) minT = t;
    if (t > maxT) maxT = t;
    if (pr < minP) minP = pr;
    if (pr > maxP) maxP = pr;
  }
  // Pad ranges so markers don't sit on the axis.
  const padT = (maxT - minT) * 0.1 || 1;
  const padP = (maxP - minP) * 0.1 || 1;
  return {
    minT: minT - padT,
    maxT: maxT + padT,
    minP: Math.max(0, minP - padP),
    maxP: maxP + padP,
  };
}

// ---------------------------------------------------------------------------
// Component (inline SVG — no external chart library)
// ---------------------------------------------------------------------------

interface HoverState {
  seriesKey: string;
  point: PressureTemperaturePoint;
  cx: number;
  cy: number;
}

export function PressureTemperatureChart({
  sku,
  seriesVariantCode,
  width = DEFAULT_WIDTH,
  height = DEFAULT_HEIGHT,
}: PressureTemperatureChartProps) {
  const ptQuery = useProductPressureTemperature(sku, seriesVariantCode);
  const [hover, setHover] = useState<HoverState | null>(null);

  const points = ptQuery.data?.points ?? [];
  const groups = useMemo(() => groupBySeries(points), [points]);
  const ranges = useMemo(() => computeRanges(points), [points]);

  // Inner plot region.
  const innerW = width - MARGIN.left - MARGIN.right;
  const innerH = height - MARGIN.top - MARGIN.bottom;

  const xScale = (t: number): number => {
    if (!ranges) return 0;
    if (ranges.maxT === ranges.minT) return innerW / 2;
    return ((t - ranges.minT) / (ranges.maxT - ranges.minT)) * innerW;
  };
  const yScale = (p: number): number => {
    if (!ranges) return 0;
    if (ranges.maxP === ranges.minP) return innerH / 2;
    return innerH - ((p - ranges.minP) / (ranges.maxP - ranges.minP)) * innerH;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pressure / Temperature</CardTitle>
        <CardDescription>
          Maximum allowed pressure as a function of working temperature.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {ptQuery.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : ptQuery.isError ? (
          <p className="text-sm text-destructive">
            Failed to load P-T curve.
          </p>
        ) : points.length === 0 || !ranges ? (
          <p className="text-sm text-muted-foreground">
            Sin curva P-T disponible
          </p>
        ) : (
          <div className="relative">
            <svg
              role="img"
              aria-label="Pressure-temperature curve"
              width={width}
              height={height}
              viewBox={`0 0 ${width} ${height}`}
              className="max-w-full"
            >
              {/* Plot area background + axes */}
              <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
                {/* Y axis */}
                <line
                  x1={0}
                  y1={0}
                  x2={0}
                  y2={innerH}
                  stroke="currentColor"
                  className="text-border"
                  strokeWidth={1}
                />
                {/* X axis */}
                <line
                  x1={0}
                  y1={innerH}
                  x2={innerW}
                  y2={innerH}
                  stroke="currentColor"
                  className="text-border"
                  strokeWidth={1}
                />
                {/* Y ticks (5 evenly spaced) */}
                {Array.from({ length: 5 }, (_, i) => {
                  const frac = i / 4;
                  const value =
                    ranges.minP + frac * (ranges.maxP - ranges.minP);
                  const y = innerH - frac * innerH;
                  return (
                    <g key={`yt-${i}`}>
                      <line
                        x1={-4}
                        y1={y}
                        x2={0}
                        y2={y}
                        stroke="currentColor"
                        className="text-border"
                      />
                      <text
                        x={-8}
                        y={y}
                        dy="0.32em"
                        textAnchor="end"
                        className="fill-muted-foreground text-[10px]"
                      >
                        {value.toFixed(0)}
                      </text>
                    </g>
                  );
                })}
                {/* X ticks (5 evenly spaced) */}
                {Array.from({ length: 5 }, (_, i) => {
                  const frac = i / 4;
                  const value =
                    ranges.minT + frac * (ranges.maxT - ranges.minT);
                  const x = frac * innerW;
                  return (
                    <g key={`xt-${i}`}>
                      <line
                        x1={x}
                        y1={innerH}
                        x2={x}
                        y2={innerH + 4}
                        stroke="currentColor"
                        className="text-border"
                      />
                      <text
                        x={x}
                        y={innerH + 16}
                        textAnchor="middle"
                        className="fill-muted-foreground text-[10px]"
                      >
                        {value.toFixed(0)}
                      </text>
                    </g>
                  );
                })}
                {/* Axis labels */}
                <text
                  x={innerW / 2}
                  y={innerH + 32}
                  textAnchor="middle"
                  className="fill-muted-foreground text-xs"
                >
                  Temperature (degC)
                </text>
                <text
                  transform={`translate(-44, ${innerH / 2}) rotate(-90)`}
                  textAnchor="middle"
                  className="fill-muted-foreground text-xs"
                >
                  Pressure (bar)
                </text>

                {/* Series polylines */}
                {Array.from(groups.entries()).map(([key, series], idx) => {
                  const colour = SERIES_COLOURS[idx % SERIES_COLOURS.length];
                  const path = series
                    .map(
                      (p) =>
                        `${xScale(Number(p.temperature_c))},${yScale(
                          Number(p.pressure_max_bar),
                        )}`,
                    )
                    .join(" ");
                  return (
                    <g key={`series-${key || "default"}`}>
                      <polyline
                        points={path}
                        fill="none"
                        stroke={colour}
                        strokeWidth={2}
                        data-series-key={key || "default"}
                      />
                      {series.map((pt) => {
                        const cx = xScale(Number(pt.temperature_c));
                        const cy = yScale(Number(pt.pressure_max_bar));
                        return (
                          <circle
                            key={pt.id}
                            cx={cx}
                            cy={cy}
                            r={4}
                            fill={colour}
                            data-testid={`pt-marker-${pt.id}`}
                            onMouseEnter={() =>
                              setHover({
                                seriesKey: key || "default",
                                point: pt,
                                cx,
                                cy,
                              })
                            }
                            onMouseLeave={() => setHover(null)}
                          />
                        );
                      })}
                    </g>
                  );
                })}

                {/* Tooltip */}
                {hover ? (
                  <g
                    transform={`translate(${hover.cx + 8}, ${hover.cy - 8})`}
                    pointerEvents="none"
                  >
                    <rect
                      x={0}
                      y={-32}
                      width={140}
                      height={36}
                      rx={4}
                      className="fill-background stroke-border"
                      strokeWidth={1}
                    />
                    <text
                      x={6}
                      y={-18}
                      className="fill-foreground text-[11px]"
                    >
                      {Number(hover.point.temperature_c).toFixed(1)} degC
                    </text>
                    <text
                      x={6}
                      y={-4}
                      className="fill-foreground text-[11px]"
                    >
                      {Number(hover.point.pressure_max_bar).toFixed(1)} bar
                      {hover.seriesKey !== "default"
                        ? ` (${hover.seriesKey})`
                        : ""}
                    </text>
                  </g>
                ) : null}
              </g>
            </svg>

            {/* Legend — only when more than one series */}
            {groups.size > 1 ? (
              <ul
                data-testid="pt-legend"
                className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground"
              >
                {Array.from(groups.keys()).map((key, idx) => (
                  <li
                    key={`legend-${key || "default"}`}
                    className="flex items-center gap-1"
                  >
                    <span
                      aria-hidden="true"
                      className="inline-block h-2 w-3 rounded-sm"
                      style={{
                        backgroundColor:
                          SERIES_COLOURS[idx % SERIES_COLOURS.length],
                      }}
                    />
                    {key || "default"}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default PressureTemperatureChart;
