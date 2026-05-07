"use client";

import * as React from "react";

/**
 * Devuelve un valor debounced. El valor sólo se propaga tras `ms` milisegundos
 * sin cambios. Útil para queries (cmd-K, autocomplete) donde no se quiere
 * disparar fetch en cada keystroke.
 */
export function useDebouncedValue<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = React.useState(value);

  React.useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);

  return debounced;
}
