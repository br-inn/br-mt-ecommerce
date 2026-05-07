import * as React from "react";
import { MT } from "./tokens";

// MT corporate mark — italic "M" with horizontal accent bar.
// Mirrors the MT logo SVG used throughout the design exploration; the gradient
// is the same blue ramp used by the topbar / sidebar accent stripes.
export function MTMark({
  size = 28,
  mono = false,
}: {
  size?: number;
  mono?: boolean;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      className="block shrink-0"
      aria-hidden
    >
      <defs>
        <linearGradient id="mtGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={MT.brandDeep} />
          <stop offset="55%" stopColor={MT.brand} />
          <stop offset="100%" stopColor={MT.brandLight} />
        </linearGradient>
      </defs>
      <rect
        x="2"
        y="2"
        width="60"
        height="60"
        rx="10"
        fill={mono ? "transparent" : "url(#mtGrad)"}
        stroke={mono ? MT.brand : "none"}
        strokeWidth={mono ? 2 : 0}
      />
      <g fill={mono ? MT.brand : "white"}>
        <polygon points="14,46 22,18 28,18 24,46" />
        <polygon points="24,46 32,18 36,18 28,46" />
        <polygon points="34,46 42,18 50,18 44,46" />
        <rect x="12" y="50" width="40" height="3.2" rx="1.2" />
      </g>
    </svg>
  );
}

export function MTWordmark({ height = 22 }: { height?: number }) {
  return (
    <span className="inline-flex items-center gap-2" style={{ height }}>
      <MTMark size={height} />
      <span
        className="leading-none"
        style={{
          fontFamily: "var(--font-mt-sans)",
          fontWeight: 700,
          fontStyle: "italic",
          fontSize: height * 0.78,
          color: MT.brandDeep,
          letterSpacing: -0.6,
        }}
      >
        MT
        <span style={{ color: MT.brand, fontWeight: 600, fontStyle: "normal" }}>
          ·ME
        </span>
      </span>
    </span>
  );
}
