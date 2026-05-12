#!/usr/bin/env node
/**
 * i18n Coverage Audit — US-1A-07-04-AR
 *
 * Reads messages/es.json as the source of truth.
 * For each locale (en, ar) verifies all keys exist and have non-empty values.
 * Exits with code 1 if any locale has coverage < 100%.
 */

const fs = require("fs");
const path = require("path");

const messagesDir = path.resolve(__dirname, "../messages");
const SOURCE_LOCALE = "es";
const CHECK_LOCALES = ["en", "ar"];

/**
 * Recursively extracts all dot-notation keys from a nested object.
 * @param {Record<string, unknown>} obj
 * @param {string} prefix
 * @returns {string[]}
 */
function getKeys(obj, prefix = "") {
  const keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      keys.push(...getKeys(v, full));
    } else {
      keys.push(full);
    }
  }
  return keys;
}

/**
 * Resolves a dot-notation key path against a nested object.
 * Returns undefined if the path does not exist.
 * @param {Record<string, unknown>} obj
 * @param {string} keyPath
 * @returns {unknown}
 */
function getValue(obj, keyPath) {
  return keyPath.split(".").reduce((cur, part) => {
    if (cur === null || cur === undefined || typeof cur !== "object") return undefined;
    return cur[part];
  }, obj);
}

function loadJson(locale) {
  const filePath = path.join(messagesDir, `${locale}.json`);
  if (!fs.existsSync(filePath)) {
    console.error(`ERROR: File not found: ${filePath}`);
    process.exit(2);
  }
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

// ── Main ──────────────────────────────────────────────────────────────────────

const source = loadJson(SOURCE_LOCALE);
const sourceKeys = getKeys(source);
const total = sourceKeys.length;

let failed = false;

console.log(`\ni18n Coverage Audit  (source: ${SOURCE_LOCALE}, ${total} keys)\n`);

for (const locale of CHECK_LOCALES) {
  const data = loadJson(locale);
  const localeKeys = new Set(getKeys(data));

  const missing = [];
  const empty = [];

  for (const key of sourceKeys) {
    if (!localeKeys.has(key)) {
      missing.push(key);
    } else {
      const val = getValue(data, key);
      if (val === "" || val === null || val === undefined) {
        empty.push(key);
      }
    }
  }

  const issues = [...missing, ...empty];
  const covered = total - issues.length;
  const pct = ((covered / total) * 100).toFixed(1);

  if (issues.length === 0) {
    console.log(`  ✅ ${locale}: 100% (${total} keys)`);
  } else {
    failed = true;
    console.log(`  ❌ ${locale}: ${pct}% (${issues.length} issues — ${covered}/${total} keys ok)`);
    if (missing.length > 0) {
      console.log(`     Missing keys (${missing.length}):`);
      missing.forEach((k) => console.log(`       - ${k}`));
    }
    if (empty.length > 0) {
      console.log(`     Empty values (${empty.length}):`);
      empty.forEach((k) => console.log(`       - ${k}`));
    }
  }
}

console.log("");

if (failed) {
  console.error("FAIL: One or more locales have coverage < 100%.");
  process.exit(1);
} else {
  console.log("All locales at 100% coverage.");
  process.exit(0);
}
