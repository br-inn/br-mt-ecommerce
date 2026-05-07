// Design tokens mirroring the MT Pricing MDM UX exploration.
// Use these for inline-style values that are tied to the design (waterfall bars,
// tinted cards). For everyday layout, prefer the matching `mt-*` Tailwind tokens.

export const MT = {
  brand: "#1f4fe0",
  brandLight: "#5c8bff",
  brandDeep: "#143aab",
  brandSoft: "#eef3ff",
  brandSofter: "#f6f8ff",
  brandBorder: "#cfdbfa",

  bg: "#f7f8fa",
  surface: "#ffffff",
  surface2: "#fafbfc",
  surface3: "#f2f4f7",
  border: "#e5e8ec",
  borderStrong: "#d2d6dc",

  ink: "#0f172a",
  ink2: "#334155",
  ink3: "#64748b",
  ink4: "#94a3b8",

  success: "#0e9f6e",
  successSoft: "#e8f5ee",
  successBorder: "#c7e8d7",
  warning: "#b26a00",
  warningSoft: "#fcf3dd",
  warningBorder: "#f1dda7",
  danger: "#c8341b",
  dangerSoft: "#fbe9e5",
  dangerBorder: "#f2c8bf",
} as const;

export const MT_FONT = {
  sans: "var(--font-mt-sans)",
  mono: "var(--font-mt-mono)",
  arabic: "var(--font-mt-arabic)",
} as const;

export type MtTone =
  | "neutral"
  | "brand"
  | "success"
  | "warning"
  | "danger"
  | "ghost";
