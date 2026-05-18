"use client";

import { AlertTriangle, FlaskConical, Inbox } from "lucide-react";
import { MtButton } from "./primitives";
import { MT } from "./tokens";

// Skeleton placeholder for loading rows / cards.
export function MtSkeleton({
  className,
  width,
  height = 16,
}: {
  className?: string;
  width?: string | number;
  height?: number;
}) {
  return (
    <span
      className={`inline-block animate-pulse rounded-[4px] ${className ?? ""}`}
      style={{
        width,
        height,
        background: `linear-gradient(90deg, ${MT.surface3} 0%, ${MT.surface2} 50%, ${MT.surface3} 100%)`,
      }}
    />
  );
}

export function MtEmpty({
  title,
  hint,
  icon = <Inbox className="size-6" strokeWidth={1.4} />,
  cta,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
  cta?: React.ReactNode;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center"
      style={{ color: MT.ink3 }}
    >
      <div
        className="grid size-10 place-items-center rounded-full"
        style={{ background: MT.surface3, color: MT.ink4 }}
      >
        {icon}
      </div>
      <div className="text-[13px] font-semibold" style={{ color: MT.ink }}>
        {title}
      </div>
      {hint ? <div className="text-xs">{hint}</div> : null}
      {cta ? <div className="mt-2">{cta}</div> : null}
    </div>
  );
}

export function MtError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="flex items-center gap-3 rounded-md border px-4 py-3 text-[12.5px]"
      style={{
        background: MT.dangerSoft,
        borderColor: MT.dangerBorder,
        color: MT.danger,
      }}
    >
      <AlertTriangle className="size-4 shrink-0" />
      <span className="flex-1">{message}</span>
      {onRetry ? (
        <MtButton size="sm" tone="ghost" onClick={onRetry}>
          Reintentar
        </MtButton>
      ) : null}
    </div>
  );
}

// "Demo data — backend pendiente" banner for screens whose backend isn't shipped yet.
export function MtDemoBanner({ note }: { note: string }) {
  return (
    <div
      className="flex items-center gap-2.5 border-b px-6 py-2 text-[12px]"
      style={{
        background: MT.warningSoft,
        borderColor: MT.warningBorder,
        color: MT.warning,
      }}
    >
      <FlaskConical className="size-3.5" />
      <span>
        <strong>Datos demo</strong> — esta pantalla aún muestra el prototipo.
        Backend pendiente: {note}
      </span>
    </div>
  );
}
