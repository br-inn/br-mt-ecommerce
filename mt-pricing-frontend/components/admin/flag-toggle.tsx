"use client";

import * as React from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type AdminFlag,
  type AdminFlagPatchPayload,
} from "@/lib/api/endpoints/admin-flags";
import { usePatchAdminFlag } from "@/lib/hooks/admin/use-flags";

interface Props {
  flag: AdminFlag;
  /** RBAC: si false, controles deshabilitados (sólo lectura). */
  canWrite: boolean;
}

/**
 * Toggle de feature flag — soporta `bool`, `int` y `string`.
 *
 * - `bool`: Switch ON/OFF.
 * - `int`/`string`: Input + botón "Guardar" (debounced via blur).
 *
 * Edits muestran un toast `success/error`. Errores de RBAC del backend
 * se mapean a un mensaje localizado.
 */
export function FlagToggle({ flag, canWrite }: Props) {
  const t = useTranslations("admin.flags");
  const tCommon = useTranslations("common");
  const patch = usePatchAdminFlag(flag.key);

  // Derived state: si `flag.value` cambia (refetch tras mutate / kill-switch),
  // resincronizamos el draft sin un effect (anti-pattern de React 19 / RSC).
  const upstream = String(flag.value);
  const [draft, setDraft] = React.useState<string>(upstream);
  const [lastUpstream, setLastUpstream] = React.useState<string>(upstream);
  if (lastUpstream !== upstream) {
    setLastUpstream(upstream);
    setDraft(upstream);
  }

  const submit = async (payload: AdminFlagPatchPayload) => {
    try {
      await patch.mutateAsync(payload);
      toast.success(t("toast.updated", { key: flag.key }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("errors.patchFailed"));
    }
  };

  const onToggleBool = () => {
    const next = !(flag.value as boolean);
    void submit({ value: next });
  };

  const onCommitText = () => {
    if (flag.value_type === "int") {
      const num = Number(draft);
      if (!Number.isFinite(num)) {
        toast.error(t("errors.invalidNumber"));
        return;
      }
      void submit({ value: num });
    } else {
      void submit({ value: draft });
    }
  };

  if (flag.value_type === "bool") {
    const on = flag.value === true;
    return (
      <div className="flex items-center gap-3">
        <Button
          type="button"
          size="sm"
          variant={on ? "default" : "outline"}
          onClick={onToggleBool}
          disabled={!canWrite || patch.isPending}
          aria-pressed={on}
          data-testid={`flag-toggle-${flag.key}`}
        >
          {on ? tCommon("yes") : tCommon("no")}
        </Button>
        {flag.is_kill_switch ? (
          <Badge variant="destructive" className="text-[10px] uppercase">
            {t("killSwitchTag")}
          </Badge>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Input
        type={flag.value_type === "int" ? "number" : "text"}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        disabled={!canWrite || patch.isPending}
        className="h-8 w-32 font-mono text-xs"
        data-testid={`flag-input-${flag.key}`}
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={onCommitText}
        disabled={
          !canWrite || patch.isPending || draft === String(flag.value)
        }
      >
        {tCommon("save")}
      </Button>
    </div>
  );
}
