import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils/cn";
import { MT, type MtTone } from "./tokens";

// ────────────────────────────────────────────────────────────────────
// Pill — semaphore badge with optional dot
// ────────────────────────────────────────────────────────────────────
const PILL_TONES: Record<MtTone, { bg: string; fg: string; bd: string }> = {
  neutral: { bg: MT.surface3, fg: MT.ink2, bd: MT.border },
  brand: { bg: MT.brandSoft, fg: MT.brand, bd: MT.brandBorder },
  success: { bg: MT.successSoft, fg: MT.success, bd: MT.successBorder },
  warning: { bg: MT.warningSoft, fg: MT.warning, bd: MT.warningBorder },
  danger: { bg: MT.dangerSoft, fg: MT.danger, bd: MT.dangerBorder },
  ghost: { bg: "transparent", fg: MT.ink3, bd: MT.border },
};

export function Pill({
  tone = "neutral",
  mono = false,
  dot = false,
  children,
  className,
}: {
  tone?: MtTone;
  mono?: boolean;
  dot?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  const t = PILL_TONES[tone];
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-[4px] border px-1.5 text-[11px] font-medium leading-none",
        mono ? "mt-mono" : "mt-sans",
        className,
      )}
      style={{ backgroundColor: t.bg, color: t.fg, borderColor: t.bd }}
    >
      {dot ? (
        <span className="size-[5px] rounded-full" style={{ backgroundColor: "currentColor" }} />
      ) : null}
      {children}
    </span>
  );
}

// ────────────────────────────────────────────────────────────────────
// MtButton — design-system button (use shadcn `Button` for forms; this one
// matches the MT prototype's tight density + neutral/primary/ghost/danger tones).
// ────────────────────────────────────────────────────────────────────
type BtnTone = "neutral" | "primary" | "ghost" | "danger";
type BtnSize = "sm" | "md";

const BTN_TONES: Record<BtnTone, { bg: string; fg: string; bd: string }> = {
  neutral: { bg: MT.surface, fg: MT.ink2, bd: MT.border },
  primary: { bg: MT.brand, fg: "#ffffff", bd: MT.brand },
  ghost: { bg: "transparent", fg: MT.ink2, bd: "transparent" },
  danger: { bg: "transparent", fg: MT.danger, bd: MT.dangerBorder },
};

const BTN_SIZES: Record<BtnSize, { h: number; px: number; fz: number }> = {
  sm: { h: 26, px: 10, fz: 12 },
  md: { h: 30, px: 12, fz: 13 },
};

export const MtButton = React.forwardRef<
  HTMLButtonElement,
  Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
    tone?: BtnTone;
    size?: BtnSize;
    icon?: React.ReactNode;
    children?: React.ReactNode;
    asChild?: boolean;
  }
>(function MtButton(
  { tone = "neutral", size = "md", icon, children, className, style, asChild, ...rest },
  ref,
) {
  const t = BTN_TONES[tone];
  const s = BTN_SIZES[size];
  const Comp = asChild ? Slot : "button";
  const buttonOnlyProps = asChild ? {} : { type: "button" as const };
  return (
    <Comp
      ref={ref as React.Ref<HTMLButtonElement & HTMLAnchorElement>}
      {...buttonOnlyProps}
      className={cn(
        "mt-sans inline-flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[5px] border font-medium leading-none transition-[background-color,border-color,box-shadow,filter] duration-150",
        "hover:brightness-[0.97] active:brightness-95 disabled:opacity-50 disabled:cursor-not-allowed",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-mt-brand focus-visible:ring-offset-1 focus-visible:ring-offset-mt-surface",
        className,
      )}
      style={{
        height: s.h,
        padding: `0 ${s.px}px`,
        fontSize: s.fz,
        backgroundColor: t.bg,
        color: t.fg,
        borderColor: t.bd,
        ...style,
      }}
      {...rest}
    >
      {asChild ? (
        children
      ) : (
        <>
          {icon}
          {children}
        </>
      )}
    </Comp>
  );
});

// ────────────────────────────────────────────────────────────────────
// Kbd — keyboard hint
// ────────────────────────────────────────────────────────────────────
export function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="mt-mono inline-flex h-[17px] items-center rounded-[3.5px] border px-1.5 text-[10.5px] leading-none"
      style={{
        color: MT.ink3,
        backgroundColor: MT.surface,
        borderColor: MT.border,
        boxShadow: `0 1px 0 ${MT.border}`,
      }}
    >
      {children}
    </span>
  );
}

// ────────────────────────────────────────────────────────────────────
// Sparkline — bare SVG sparkline, no axis
// ────────────────────────────────────────────────────────────────────
export function Sparkline({
  data,
  color = MT.brand,
  width = 240,
  height = 28,
}: {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const path = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / (max - min || 1)) * height;
      return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const fill = `${path} L${width},${height} L0,${height} Z`;
  return (
    <svg width={width} height={height} className="block">
      <path d={fill} fill={color} fillOpacity={0.08} />
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ────────────────────────────────────────────────────────────────────
// KpiCard — accent-bar + label + big value + optional sparkline
// ────────────────────────────────────────────────────────────────────
const KPI_RING: Record<MtTone, string> = {
  neutral: MT.border,
  brand: MT.brandBorder,
  success: MT.successBorder,
  warning: MT.warningBorder,
  danger: MT.dangerBorder,
  ghost: MT.border,
};

export function KpiCard({
  label,
  value,
  sub,
  tone = "neutral",
  badge,
  spark,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  tone?: MtTone;
  badge?: React.ReactNode;
  spark?: React.ReactNode;
}) {
  return (
    <div
      className="relative flex flex-col gap-2 overflow-hidden rounded-lg border bg-mt-surface px-4 py-[14px]"
      style={{ borderColor: MT.border }}
    >
      <div className="flex items-center justify-between">
        <span
          className="mt-mono text-[11.5px] uppercase tracking-[0.6px]"
          style={{ color: MT.ink3 }}
        >
          {label}
        </span>
        {badge ? (
          <Pill tone={tone} dot>
            {badge}
          </Pill>
        ) : null}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span
          className="mt-tnum text-[28px] font-semibold tracking-[-0.6px]"
          style={{ color: MT.ink }}
        >
          {value}
        </span>
        {sub ? (
          <span className="text-xs" style={{ color: MT.ink3 }}>
            {sub}
          </span>
        ) : null}
      </div>
      {spark}
      <span
        className="absolute left-0 top-0 bottom-0 w-[3px]"
        style={{ backgroundColor: KPI_RING[tone] }}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Table primitives — dense, mono-uppercase headers
// ────────────────────────────────────────────────────────────────────
export function MtTh({
  children,
  className,
  style,
  ...rest
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "mt-mono border-b px-2.5 py-2 text-left text-[10.5px] font-medium uppercase tracking-[0.5px]",
        className,
      )}
      style={{
        color: MT.ink3,
        borderColor: MT.border,
        backgroundColor: MT.surface2,
        ...style,
      }}
      {...rest}
    >
      {children}
    </th>
  );
}

export function MtTd({
  children,
  mono,
  className,
  style,
  ...rest
}: React.TdHTMLAttributes<HTMLTableCellElement> & { mono?: boolean | undefined }) {
  return (
    <td
      className={cn(
        "border-b px-2.5 py-2 text-[12.5px]",
        mono ? "mt-mono mt-tnum" : "mt-sans",
        className,
      )}
      style={{
        color: MT.ink2,
        borderColor: MT.border,
        ...style,
      }}
      {...rest}
    >
      {children}
    </td>
  );
}

// ────────────────────────────────────────────────────────────────────
// Thumb — placeholder image swatch with diagonal hatch
// ────────────────────────────────────────────────────────────────────
export function Thumb({ size = 28 }: { size?: number }) {
  return (
    <div
      className="grid shrink-0 place-items-center rounded-[4px] border"
      style={{
        width: size,
        height: size,
        background: `repeating-linear-gradient(45deg, ${MT.surface3} 0 ${
          size > 32 ? 6 : 4
        }px, ${MT.surface2} ${size > 32 ? 6 : 4}px ${size > 32 ? 12 : 8}px)`,
        borderColor: MT.border,
        color: MT.ink4,
      }}
    >
      <svg
        width={Math.round(size * 0.4)}
        height={Math.round(size * 0.4)}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </svg>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// QualityBadge — data_quality status (complete / partial / blocked)
// ────────────────────────────────────────────────────────────────────
export function QualityBadge({
  v,
}: {
  v: "complete" | "partial" | "blocked";
}) {
  if (v === "partial") return <Pill tone="warning" dot>partial</Pill>;
  if (v === "blocked") return <Pill tone="danger" dot>blocked</Pill>;
  return <Pill tone="success" dot>complete</Pill>;
}

// ────────────────────────────────────────────────────────────────────
// Translation status — three dots (EN / ES / AR), approved · draft · missing
// ────────────────────────────────────────────────────────────────────
export type TStatusVal = "a" | "d" | "n"; // approved · draft · missing

export function TStatusDots({
  en,
  es,
  ar,
}: {
  en: TStatusVal;
  es: TStatusVal;
  ar: TStatusVal;
}) {
  const dot = (s: TStatusVal) => {
    if (s === "a")
      return <span className="inline-block size-[7px] rounded-full" style={{ background: MT.success }} />;
    if (s === "d")
      return <span className="inline-block size-[7px] rounded-full" style={{ background: MT.warning }} />;
    return (
      <span
        className="inline-block size-[7px] rounded-full border"
        style={{ borderColor: MT.borderStrong }}
      />
    );
  };
  return (
    <span
      className="mt-mono inline-flex items-center gap-1.5 text-[10.5px]"
      style={{ color: MT.ink3 }}
    >
      <span className="inline-flex items-center gap-[3px]">EN {dot(en)}</span>
      <span className="inline-flex items-center gap-[3px]">ES {dot(es)}</span>
      <span className="inline-flex items-center gap-[3px]">AR {dot(ar)}</span>
    </span>
  );
}

// Compact glyph variant for the SKU list table.
export function TStatusGlyphs({
  t,
}: {
  t: { en: TStatusVal; es: TStatusVal; ar: TStatusVal };
}) {
  const dot = (s: TStatusVal) => {
    if (s === "a") return <span style={{ color: MT.success }}>●</span>;
    if (s === "d") return <span style={{ color: MT.warning }}>▲</span>;
    return <span style={{ color: MT.ink4 }}>○</span>;
  };
  return (
    <span className="mt-mono text-[11px] tracking-[1.5px]">
      {dot(t.en)} {dot(t.es)} {dot(t.ar)}
    </span>
  );
}

// ────────────────────────────────────────────────────────────────────
// ScorePill — semaphore numeric score (0–100), used by Validación de matches
// ────────────────────────────────────────────────────────────────────
export function ScorePill({
  score,
  size = "md",
}: {
  score: number;
  size?: "md" | "lg";
}) {
  const tone =
    score >= 70
      ? { bg: MT.successSoft, fg: MT.success, bd: MT.successBorder, dot: MT.success, label: "Alto" }
      : score >= 40
        ? { bg: MT.warningSoft, fg: MT.warning, bd: MT.warningBorder, dot: MT.warning, label: "Medio" }
        : { bg: MT.dangerSoft, fg: MT.danger, bd: MT.dangerBorder, dot: MT.danger, label: "Bajo" };
  const h = size === "lg" ? 24 : 20;
  return (
    <span
      className="mt-mono inline-flex items-center gap-1.5 whitespace-nowrap rounded-[4px] border font-semibold leading-none"
      style={{
        height: h,
        padding: size === "lg" ? "0 9px" : "0 7px",
        fontSize: size === "lg" ? 12 : 11,
        backgroundColor: tone.bg,
        color: tone.fg,
        borderColor: tone.bd,
      }}
    >
      <span className="size-1.5 rounded-full" style={{ backgroundColor: tone.dot }} />
      {score}
      {size === "lg" ? (
        <span className="mt-sans font-medium opacity-70">· {tone.label}</span>
      ) : null}
    </span>
  );
}

// ────────────────────────────────────────────────────────────────────
// FilterChip — toolbar filter tab with optional count
// ────────────────────────────────────────────────────────────────────
export function FilterChip({
  label,
  count,
  active = false,
  tone = "neutral",
}: {
  label: string;
  count?: number | undefined;
  active?: boolean | undefined;
  tone?: ("neutral" | "brand") | undefined;
}) {
  const isActive = !!active;
  const palette =
    tone === "brand"
      ? {
          bd: isActive ? MT.brand : MT.border,
          bg: isActive ? MT.brandSoft : MT.surface,
          fg: isActive ? MT.brandDeep : MT.ink2,
          countBg: isActive ? "#ffffff" : MT.surface3,
          countFg: isActive ? MT.brand : MT.ink3,
        }
      : {
          bd: MT.border,
          bg: isActive ? MT.ink : MT.surface,
          fg: isActive ? "#ffffff" : MT.ink2,
          countBg: isActive ? "rgba(255,255,255,.18)" : MT.surface3,
          countFg: isActive ? "#ffffff" : MT.ink3,
        };
  return (
    <span
      className={cn(
        "inline-flex h-7 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-[5px] border px-2.5 text-xs",
        isActive ? "font-semibold" : "font-medium",
      )}
      style={{ backgroundColor: palette.bg, color: palette.fg, borderColor: palette.bd }}
    >
      {label}
      {count !== undefined ? (
        <span
          className="mt-mono rounded-[3px] px-1.5 py-px text-[10.5px] leading-[1.4]"
          style={{ backgroundColor: palette.countBg, color: palette.countFg }}
        >
          {count}
        </span>
      ) : null}
    </span>
  );
}

// ────────────────────────────────────────────────────────────────────
// SectionCard — card with header + body, used by every screen
// ────────────────────────────────────────────────────────────────────
export function SectionCard({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <div
      className={cn("overflow-hidden rounded-lg border bg-mt-surface", className)}
      style={{ borderColor: MT.border }}
    >
      {title || subtitle || actions ? (
        <div
          className="flex items-center justify-between border-b px-4 py-3"
          style={{ borderColor: MT.border }}
        >
          <div className="flex flex-col gap-0.5">
            {title ? (
              <span
                className="text-[13.5px] font-semibold tracking-[-0.1px]"
                style={{ color: MT.ink }}
              >
                {title}
              </span>
            ) : null}
            {subtitle ? (
              <span className="text-[11.5px]" style={{ color: MT.ink3 }}>
                {subtitle}
              </span>
            ) : null}
          </div>
          {actions ? <div className="flex items-center gap-1.5">{actions}</div> : null}
        </div>
      ) : null}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Crumbs — page breadcrumb trail
// ────────────────────────────────────────────────────────────────────
export function Crumbs({ items }: { items: { label: string; mono?: boolean; bold?: boolean }[] }) {
  return (
    <div className="flex items-center gap-2 text-xs" style={{ color: MT.ink3 }}>
      {items.map((it, i) => (
        <React.Fragment key={`${it.label}-${i}`}>
          {i > 0 ? (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          ) : null}
          <span
            className={cn(it.mono ? "mt-mono" : "mt-sans", it.bold ? "font-semibold" : undefined)}
            style={{ color: it.bold ? MT.ink : MT.ink3 }}
          >
            {it.label}
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}
