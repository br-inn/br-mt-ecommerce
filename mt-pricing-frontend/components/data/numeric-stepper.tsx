"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils/cn";

interface NumericStepperProps {
  value: number;
  onChange: (newValue: number) => void;
  min?: number;
  max?: number;
  step?: number;
  decimals?: number;
  suffix?: string;
  className?: string;
  size?: "sm" | "md";
  "aria-label"?: string;
  /** When true, paints the stepper in MT-warning amber (indicates modified/user-edited). */
  modified?: boolean;
  disabled?: boolean;
}

export function NumericStepper({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  decimals = 0,
  suffix = "",
  className,
  size = "md",
  modified = false,
  disabled = false,
  "aria-label": ariaLabel,
}: NumericStepperProps) {
  const [draftText, setDraftText] = useState(value.toFixed(decimals));

  useEffect(() => {
    setDraftText(value.toFixed(decimals));
  }, [value, decimals]);

  const commit = (raw: string) => {
    const clean = raw.replace(",", ".").replace(suffix, "").trim();
    const parsed = parseFloat(clean);
    if (Number.isNaN(parsed)) {
      setDraftText(value.toFixed(decimals));
      return;
    }
    const clamped = Math.max(min, Math.min(max, parsed));
    onChange(clamped);
  };

  const bump = (direction: 1 | -1) => {
    const next = +(value + direction * step).toFixed(decimals);
    const clamped = Math.max(min, Math.min(max, next));
    onChange(clamped);
  };

  const sizeClasses = {
    sm: { button: "h-6 w-5 text-xs", input: "h-6 w-12 text-xs" },
    md: { button: "h-7 w-6 text-sm", input: "h-7 w-16 text-sm" },
  }[size];

  const colorClasses = modified
    ? "border-mt-warning-border bg-mt-warning-soft text-mt-warning"
    : "border-mt-border bg-white text-mt-ink";

  return (
    <div
      className={cn(
        "inline-flex items-center overflow-hidden rounded-md border",
        colorClasses,
        disabled && "opacity-50",
        className,
      )}
      role="spinbutton"
      aria-label={ariaLabel}
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
    >
      <button
        type="button"
        onClick={() => bump(-1)}
        disabled={disabled || value <= min}
        className={cn(
          "border-r font-bold transition",
          modified
            ? "border-mt-warning-border bg-mt-warning hover:bg-mt-warning-deep text-white"
            : "border-mt-border bg-mt-brand hover:bg-mt-brand-deep text-white",
          sizeClasses.button,
          "disabled:opacity-30",
        )}
        aria-label="decrement"
      >
        −
      </button>
      <input
        type="text"
        value={draftText + (suffix && !draftText.endsWith(suffix) ? suffix : "")}
        onChange={(e) => setDraftText(e.target.value.replace(suffix, ""))}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        disabled={disabled}
        className={cn(
          "mt-tnum border-0 text-center font-semibold focus:outline-none focus:ring-2 focus:ring-mt-brand-soft",
          sizeClasses.input,
        )}
      />
      <button
        type="button"
        onClick={() => bump(1)}
        disabled={disabled || value >= max}
        className={cn(
          "border-l font-bold transition",
          modified
            ? "border-mt-warning-border bg-mt-warning hover:bg-mt-warning-deep text-white"
            : "border-mt-border bg-mt-brand hover:bg-mt-brand-deep text-white",
          sizeClasses.button,
          "disabled:opacity-30",
        )}
        aria-label="increment"
      >
        +
      </button>
    </div>
  );
}
