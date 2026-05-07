// Flat config para ESLint 9 + Next 16.
// `next lint` quedó deprecado en Next 16: usar `eslint .` directamente.
// eslint-config-next@16 expone flat configs nativos (no necesita FlatCompat).
import nextConfig from "eslint-config-next";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Nota: `eslint-config-next` ya carga `eslint-plugin-jsx-a11y` y aplica sus
// reglas recomendadas. Re-incluirlo aquí provoca
// `Cannot redefine plugin "jsx-a11y"`.
const eslintConfig = [
  // Patrones a ignorar — equivalente al antiguo `.eslintignore`.
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "lib/api/types.ts",
      "next-env.d.ts",
      "tsconfig.tsbuildinfo",
    ],
  },
  ...nextConfig,
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "warn",
        { prefer: "type-imports" },
      ],
    },
  },
];

export default eslintConfig;
