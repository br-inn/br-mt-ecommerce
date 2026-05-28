import { cn } from "@/lib/utils/cn";

const SIGNAL_STYLES: Record<string, { bg: string; text: string }> = {
  PÉRDIDA: { bg: "bg-mt-danger-soft", text: "text-mt-danger" },
  FRÁGIL: { bg: "bg-mt-warning-soft", text: "text-mt-warning" },
  FINO: { bg: "bg-amber-100", text: "text-amber-900" },
  ÓPTIMO: { bg: "bg-mt-success-soft", text: "text-mt-success" },
  EXCELENTE: { bg: "bg-mt-brand-soft", text: "text-mt-brand-deep" },
};

export function SignalBadge({ signal }: { signal: string }) {
  const style = SIGNAL_STYLES[signal] ?? { bg: "bg-gray-100", text: "text-gray-700" };
  return (
    <span
      className={cn(
        "mt-mono rounded px-2 py-0.5 text-[10px] font-bold tracking-wider",
        style.bg,
        style.text,
      )}
    >
      {signal}
    </span>
  );
}
