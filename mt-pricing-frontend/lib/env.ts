import { z } from "zod";

/**
 * Soporta ambos nombres de la API key de Supabase:
 * - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (formato nuevo Supabase API v2 — recomendado)
 * - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (legacy, sigue funcionando)
 *
 * Al menos uno de los dos debe estar definido. El cliente usa publishable_key
 * si está, o cae a anon_key como fallback.
 */
/** Treats empty strings as undefined — env vars set as `KEY=` should be optional. */
const optionalNonEmpty = z
  .string()
  .optional()
  .transform((v) => (v === "" ? undefined : v));

const envSchema = z
  .object({
    NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: optionalNonEmpty,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: optionalNonEmpty,
    NEXT_PUBLIC_BACKEND_URL: z.string().url(),
    NEXT_PUBLIC_SENTRY_DSN: optionalNonEmpty,
    NEXT_PUBLIC_DEFAULT_LOCALE: z.enum(["es", "en"]).default("es"),
  })
  .refine(
    (data) =>
      Boolean(data.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY) ||
      Boolean(data.NEXT_PUBLIC_SUPABASE_ANON_KEY),
    {
      message:
        "Either NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY must be set.",
      path: ["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
    },
  );

const parsed = envSchema.safeParse({
  NEXT_PUBLIC_SUPABASE_URL: process.env["NEXT_PUBLIC_SUPABASE_URL"],
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:
    process.env["NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY"],
  NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env["NEXT_PUBLIC_SUPABASE_ANON_KEY"],
  NEXT_PUBLIC_BACKEND_URL: process.env["NEXT_PUBLIC_BACKEND_URL"],
  NEXT_PUBLIC_SENTRY_DSN: process.env["NEXT_PUBLIC_SENTRY_DSN"],
  NEXT_PUBLIC_DEFAULT_LOCALE: process.env["NEXT_PUBLIC_DEFAULT_LOCALE"],
});

if (!parsed.success) {
  // eslint-disable-next-line no-console
  console.error(
    "Invalid environment variables:",
    parsed.error.flatten().fieldErrors,
  );
  throw new Error("Invalid environment variables. Check .env.example.");
}

const data = parsed.data;

/**
 * Resuelve la key efectiva, priorizando `publishable_key` (nuevo formato).
 */
export const env = {
  ...data,
  /** Key efectiva para clientes Supabase (publishable_key | anon_key fallback). */
  NEXT_PUBLIC_SUPABASE_KEY: (data.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    data.NEXT_PUBLIC_SUPABASE_ANON_KEY) as string,
};

export default env;
