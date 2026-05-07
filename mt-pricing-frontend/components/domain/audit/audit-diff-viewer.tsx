"use client";

import * as React from "react";

import { Pill } from "@/components/mt/primitives";
import { MT } from "@/components/mt/tokens";

interface Props {
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  diff?: Record<string, unknown> | null | undefined;
  className?: string;
}

type FieldDiff = {
  field: string;
  before: unknown;
  after: unknown;
  kind: "added" | "removed" | "changed";
};

/**
 * JSON before/after diff viewer.
 *
 * UX:
 *  - Si hay payload_diff explícito del backend, lo respetamos.
 *  - Si no, computamos diff campo a campo entre `before` y `after`.
 *  - Render: 3 columnas (campo / antes / después) con pill por kind.
 *  - Fallback: collapsible JSON pretty para los casos en que before/after
 *    son arrays / nested complex.
 */
export function AuditDiffViewer({ before, after, diff, className }: Props) {
  const computed = React.useMemo<FieldDiff[]>(() => {
    if (diff && Object.keys(diff).length > 0) {
      return Object.entries(diff).map(([field, val]) => {
        // payload_diff backend shape: { field: { before: x, after: y } }
        if (
          val !== null &&
          typeof val === "object" &&
          ("before" in (val as object) || "after" in (val as object))
        ) {
          const v = val as { before?: unknown; after?: unknown };
          const hasBefore = "before" in v;
          const hasAfter = "after" in v;
          const kind: FieldDiff["kind"] = !hasBefore
            ? "added"
            : !hasAfter
              ? "removed"
              : "changed";
          return {
            field,
            before: v.before ?? null,
            after: v.after ?? null,
            kind,
          };
        }
        return { field, before: null, after: val, kind: "changed" as const };
      });
    }
    return computeDiff(before ?? {}, after ?? {});
  }, [before, after, diff]);

  if (computed.length === 0) {
    return (
      <div
        className={className}
        style={{ color: MT.ink3, fontSize: 12, padding: "8px 0" }}
      >
        Sin cambios estructurales detectados.
      </div>
    );
  }

  return (
    <div className={className}>
      <table className="w-full border-separate border-spacing-0">
        <thead>
          <tr>
            <Th>Campo</Th>
            <Th>Antes</Th>
            <Th>Después</Th>
          </tr>
        </thead>
        <tbody>
          {computed.map((d) => (
            <tr key={d.field}>
              <Td mono>
                <Pill
                  tone={
                    d.kind === "added"
                      ? "success"
                      : d.kind === "removed"
                        ? "danger"
                        : "warning"
                  }
                  mono
                >
                  {d.kind}
                </Pill>{" "}
                <span style={{ color: MT.ink2 }}>{d.field}</span>
              </Td>
              <Td mono>
                <ValueCell value={d.before} muted={d.kind === "added"} />
              </Td>
              <Td mono>
                <ValueCell value={d.after} muted={d.kind === "removed"} />
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th
      className="mt-mono border-b px-2.5 py-1.5 text-left text-[10.5px] font-medium uppercase tracking-[0.5px]"
      style={{
        color: MT.ink3,
        borderColor: MT.border,
        backgroundColor: MT.surface2,
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  mono,
}: {
  children: React.ReactNode;
  mono?: boolean | undefined;
}) {
  return (
    <td
      className={`border-b px-2.5 py-1.5 align-top text-[12px] ${mono ? "mt-mono mt-tnum" : ""}`}
      style={{ borderColor: MT.border, color: MT.ink2 }}
    >
      {children}
    </td>
  );
}

function ValueCell({
  value,
  muted,
}: {
  value: unknown;
  muted?: boolean;
}) {
  if (value === null || value === undefined) {
    return (
      <span style={{ color: MT.ink4 }}>—</span>
    );
  }
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return (
      <span style={{ color: muted ? MT.ink4 : MT.ink2 }}>
        {String(value)}
      </span>
    );
  }
  return (
    <details>
      <summary
        className="cursor-pointer text-[11px]"
        style={{ color: MT.brand }}
      >
        ver objeto
      </summary>
      <pre className="mt-1 max-w-md overflow-x-auto text-[10.5px] leading-tight">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

function computeDiff(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): FieldDiff[] {
  const keys = new Set<string>([
    ...Object.keys(before),
    ...Object.keys(after),
  ]);
  const out: FieldDiff[] = [];
  keys.forEach((k) => {
    const b = before[k];
    const a = after[k];
    if (JSON.stringify(b) === JSON.stringify(a)) return;
    const inBefore = k in before;
    const inAfter = k in after;
    out.push({
      field: k,
      before: b ?? null,
      after: a ?? null,
      kind: !inBefore ? "added" : !inAfter ? "removed" : "changed",
    });
  });
  return out;
}
