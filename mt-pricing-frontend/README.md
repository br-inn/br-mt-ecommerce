# MT Pricing Frontend

Next.js 16 + React 19 frontend skeleton for MT Pricing & MDM (Phase 1).

Stack:
- Next.js 16 (App Router, React Compiler, standalone output)
- React 19, TypeScript 5.4 (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)
- Tailwind v4 + Shadcn (new-york preset, neutral palette, brand `#0066CC`)
- Supabase Auth (`@supabase/ssr`)
- TanStack Query v5, TanStack Table v8
- next-intl (es default, en)
- Zustand (UI state), nuqs (URL state), react-hook-form + zod
- openapi-fetch + openapi-typescript (typed client)
- Vitest + Testing Library (unit), Playwright + axe-core (e2e + a11y)
- Sentry (error monitoring)

## Quickstart

Prerequisites: Node 20+, pnpm 9+.

```bash
pnpm install
cp .env.example .env.local   # fill in values
pnpm dev
```

App boots at <http://localhost:3000> with the empty shell (sidebar + topbar + dashboard placeholder + login placeholder).

## Scripts

| Script | Purpose |
| ------ | ------- |
| `pnpm dev` | Next.js dev server on `:3000` |
| `pnpm build` | Production build (standalone) |
| `pnpm start` | Run production build |
| `pnpm lint` | ESLint (Next + a11y) |
| `pnpm typecheck` | `tsc --noEmit` (strict) |
| `pnpm format` | Prettier write |
| `pnpm test` | Vitest unit tests |
| `pnpm test:e2e` | Playwright end-to-end tests |
| `pnpm openapi:gen` | Regenerate `lib/api/types.ts` from `mt-api-contract-openapi.yaml` |

## Structure

```
app/                Next.js App Router (route groups: (auth), (app))
components/         ui (shadcn), shell, auth, data, forms, domain
lib/                env, supabase, api, i18n, hooks, stores, utils, providers
messages/           es.json, en.json (next-intl)
tests/              unit (vitest), e2e (playwright)
public/             static assets
```

## Owned by other agents

| Path | Owner |
| ---- | ----- |
| `lib/supabase/middleware.ts`, `components/auth/*`, `app/(auth)/login/page.tsx` (full impl), `lib/hooks/use-user.ts` (full impl) | Agente F |
| `app/(app)/catalogo/`, `lib/api/endpoints/`, `components/domain/*` | Agente G / Agente I |
| Root `.github/workflows/`, root `docker-compose.dev.yml`, root `Caddyfile` | Agente D |
| Root `README.md`, `CONTRIBUTING.md`, `.editorconfig` | Agente E |

## Docker

```bash
docker build -t mt-pricing-frontend .
docker run -p 3000:3000 --env-file .env.local mt-pricing-frontend
```

Healthcheck endpoint: `GET /api/health` proxies `${NEXT_PUBLIC_BACKEND_URL}/health/ready`.
