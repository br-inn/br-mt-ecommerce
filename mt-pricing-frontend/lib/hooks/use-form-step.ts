"use client";

import { useCallback, useState } from "react";
import type { FieldValues, Path, UseFormReturn } from "react-hook-form";

interface UseFormStepOptions<TForm extends FieldValues> {
  total: number;
  /** Campos que validar al pasar de cada paso. Index = step index. */
  fieldsByStep: Path<TForm>[][];
  form: UseFormReturn<TForm>;
}

interface UseFormStepResult {
  step: number;
  isFirst: boolean;
  isLast: boolean;
  next: () => Promise<boolean>;
  prev: () => void;
  goTo: (target: number) => void;
}

/**
 * Hook para wizards multi-paso con react-hook-form.
 * `next()` valida los campos del paso actual antes de avanzar.
 */
export function useFormStep<TForm extends FieldValues>(
  options: UseFormStepOptions<TForm>,
): UseFormStepResult {
  const { total, fieldsByStep, form } = options;
  const [step, setStep] = useState(0);

  const next = useCallback(async () => {
    const fields = fieldsByStep[step] ?? [];
    const ok = await form.trigger(fields, { shouldFocus: true });
    if (!ok) return false;
    setStep((s) => Math.min(s + 1, total - 1));
    return true;
  }, [step, fieldsByStep, form, total]);

  const prev = useCallback(() => {
    setStep((s) => Math.max(s - 1, 0));
  }, []);

  const goTo = useCallback(
    (target: number) => {
      setStep(Math.min(Math.max(target, 0), total - 1));
    },
    [total],
  );

  return {
    step,
    isFirst: step === 0,
    isLast: step === total - 1,
    next,
    prev,
    goTo,
  };
}
