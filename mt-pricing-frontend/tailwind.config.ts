import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        brand: {
          DEFAULT: "var(--brand)",
          foreground: "var(--brand-foreground)",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        mt: {
          brand: "var(--mt-brand)",
          "brand-light": "var(--mt-brand-light)",
          "brand-deep": "var(--mt-brand-deep)",
          "brand-soft": "var(--mt-brand-soft)",
          "brand-softer": "var(--mt-brand-softer)",
          "brand-border": "var(--mt-brand-border)",
          bg: "var(--mt-bg)",
          surface: "var(--mt-surface)",
          "surface-2": "var(--mt-surface-2)",
          "surface-3": "var(--mt-surface-3)",
          border: "var(--mt-border)",
          "border-strong": "var(--mt-border-strong)",
          ink: "var(--mt-ink)",
          "ink-2": "var(--mt-ink-2)",
          "ink-3": "var(--mt-ink-3)",
          "ink-4": "var(--mt-ink-4)",
          success: "var(--mt-success)",
          "success-soft": "var(--mt-success-soft)",
          "success-border": "var(--mt-success-border)",
          warning: "var(--mt-warning)",
          "warning-soft": "var(--mt-warning-soft)",
          "warning-border": "var(--mt-warning-border)",
          danger: "var(--mt-danger)",
          "danger-soft": "var(--mt-danger-soft)",
          "danger-border": "var(--mt-danger-border)",
        },
      },
      fontFamily: {
        "mt-sans": ["var(--font-mt-sans)"],
        "mt-mono": ["var(--font-mt-mono)"],
        "mt-arabic": ["var(--font-mt-arabic)"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};

export default config;
