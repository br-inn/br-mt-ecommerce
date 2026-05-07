# ADR-028: Frontend Next.js 16 + React 19

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Supersedes: ADR-001 (parcial — capa frontend)

## Contexto

Pivot del stack de Fase 1 para alinearse con la arquitectura de referencia BR Innovation `hppt-iom` (Hppt Dashboard). El frontend debe ser:

- Modular, tipado fuerte, performante.
- Compatible con la velocidad de iteración de BR.
- Capaz de consumir un backend separado (FastAPI) vía REST/JSON.
- Con i18n nativo (ES/EN) y soporte para validación cliente.
- Con una librería de componentes consistente que reduzca tiempo de UI.

## Decisión

**Stack frontend (alineado con hppt-iom — a verificar contra el repo de referencia):**

| Capa | Tecnología | Versión target |
|------|------------|----------------|
| Framework | Next.js (App Router) | **16.x** |
| Runtime | React + **React Compiler** | **19.x** |
| Lenguaje | TypeScript estricto | 5.x |
| Estilos | Tailwind CSS | **v4** |
| UI kit | Shadcn/ui (estilo **new-york**) + Radix primitives | latest |
| Iconografía | Lucide | latest |
| Validación | Zod (compartida con schemas Pydantic vía generación o por convención) | latest |
| i18n | next-intl (ES/EN; AR es contenido, no UI) | latest |
| Data fetching | fetch + SWR / TanStack Query | TanStack Query 5.x |
| Forms | react-hook-form + zodResolver | latest |
| Tablas | TanStack Table (+ Virtual para 50k+ filas) | latest |

El frontend consume la API FastAPI (ADR-029) vía proxy Caddy (`/api/*`) o llamada directa al backend.

## Alternativas evaluadas

- **Remix / SvelteKit / Astro**: descartadas — fuera del stack BR estándar; menos maduras para casos enterprise complejos con i18n + RBAC + tablas pesadas.
- **Next.js Pages Router**: descartado — App Router + React Server Components reducen JS al cliente, mejor para tablas con miles de filas.
- **MUI / Chakra / Mantine**: descartadas en favor de Shadcn/ui (alineado con hppt-iom); Shadcn da control sobre los componentes (vendoreados en repo) sin lock-in.

## Consecuencias positivas

- **Alineamiento con hppt-iom** → tooling, plantillas y conocimiento reutilizable entre productos BR.
- **React Compiler** → optimizaciones automáticas; menos `useMemo`/`useCallback` manuales.
- **App Router + RSC** → menor JS al cliente.
- **Shadcn (new-york)** → look profesional consistente con otros productos BR.
- **Tailwind v4** → CSS engine nuevo, más rápido.

## Consecuencias negativas / riesgos

- **Next.js 16 + React 19 + Tailwind v4 son relativamente recientes** → algunos breaking changes esperables; matriz de versiones a fijar contra hppt-iom.
- **React Compiler** todavía en evolución → desactivable por componente si genera bugs.
- TI MT podría preferir un stack distinto → ADR a confirmar en S0.

## Cuándo revisar

- **S0 — gating obligatorio**: TI MT firma o pide alternativa.
- Cuando hppt-iom actualice a una versión mayor de Next.js / React / Tailwind, alinear este proyecto.
- Si un breaking change de React Compiler bloquea desarrollo, evaluar desactivar selectivamente.
