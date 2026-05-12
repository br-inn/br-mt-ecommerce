/**
 * i18n Coverage Tests — US-1A-07-04-AR
 *
 * Verifica que ar.json (y en.json) tienen cobertura 100% respecto a es.json.
 * La fuente de verdad siempre es es.json.
 */
import { describe, it, expect } from "vitest";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
import es from "../../../messages/es.json";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import ar from "../../../messages/ar.json";
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import en from "../../../messages/en.json";

function getKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null && !Array.isArray(v)
      ? getKeys(v as Record<string, unknown>, `${prefix}${k}.`)
      : [`${prefix}${k}`],
  );
}

function getValue(obj: Record<string, unknown>, keyPath: string): unknown {
  return keyPath.split(".").reduce<unknown>((cur, part) => {
    if (cur === null || cur === undefined || typeof cur !== "object") return undefined;
    return (cur as Record<string, unknown>)[part];
  }, obj);
}

const esKeys = getKeys(es as unknown as Record<string, unknown>);

describe("i18n coverage — AR (árabe UAE)", () => {
  it("AR translation has 100% key coverage vs ES", () => {
    const arKeys = new Set(getKeys(ar as unknown as Record<string, unknown>));
    const missing = esKeys.filter((k) => !arKeys.has(k));
    expect(missing, `Claves faltantes en ar.json: ${missing.join(", ")}`).toEqual([]);
  });

  it("AR translation has no empty string values", () => {
    const empty = esKeys.filter((k) => {
      const val = getValue(ar as unknown as Record<string, unknown>, k);
      return val === "" || val === null || val === undefined;
    });
    expect(empty, `Valores vacíos en ar.json: ${empty.join(", ")}`).toEqual([]);
  });
});

describe("i18n coverage — EN (inglés)", () => {
  it("EN translation has 100% key coverage vs ES", () => {
    const enKeys = new Set(getKeys(en as unknown as Record<string, unknown>));
    const missing = esKeys.filter((k) => !enKeys.has(k));
    expect(missing, `Claves faltantes en en.json: ${missing.join(", ")}`).toEqual([]);
  });

  it("EN translation has no empty string values", () => {
    const empty = esKeys.filter((k) => {
      const val = getValue(en as unknown as Record<string, unknown>, k);
      return val === "" || val === null || val === undefined;
    });
    expect(empty, `Valores vacíos en en.json: ${empty.join(", ")}`).toEqual([]);
  });
});
