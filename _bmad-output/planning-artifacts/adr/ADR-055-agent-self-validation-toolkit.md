# ADR-055: Agent Self-Validation Toolkit (chrome-devtools-mcp + supabase-mcp)

- Status: proposed
- Date: 2026-05-07
- Deciders: Pablo Sierra (BR), TI MT
- Related: production-readiness-master-plan.md, agent-self-validation-toolkit.md

## Contexto

Durante el bootstrap de Sprint 1 (sesión 2026-05-07) se debuggearon 12+ issues
heterogéneos: conexión Supabase, password DB, config Tailwind v4 vs v3, Next.js
16 + React 19 + Turbopack vs webpack, next-intl@4 plugin, Caddy reverse proxy
WebSocket, allowedDevOrigins, pooler region, etc.

Cada issue requirió ciclos de "yo te digo qué probar — vos pegás logs/screenshot
— yo te digo siguiente paso". Con tools de inspección directa (browser real con
sesión + DB query directo), la mayoría se hubieran resuelto en 2-3 turnos en
lugar de 8-10.

Ejemplos concretos donde esto hubiera reducido fricción:

| Issue | Sin tools | Con tools |
|-------|-----------|-----------|
| Region Supabase pooler incorrecta | Probé `eu-central-1`, falló, el usuario tuvo que ir a Dashboard, copiar string | `supabase-mcp.list_projects` me daba la región directo |
| Password DB inválido | El usuario pegó password, falló auth, le pedí reset desde Dashboard | `supabase-mcp` puede generar/rotar password |
| Errores consola browser | Le pedí copy-paste de logs Chrome | `chrome-devtools-mcp.get_console_messages` los traía directo |
| Estado tabla `users` post-login | Le pedí query en SQL Editor | `supabase-mcp.execute_sql` los listaba |
| WebSocket 502 Caddy | Le pedí logs frontend + curl-tests | `chrome-devtools-mcp` me dio el error completo de upgrade |

## Decisión

Adoptar **2 MCP servers Tier 1** desde Sprint 1:

1. **`chrome-devtools-mcp`** (https://github.com/ChromeDevTools/chrome-devtools-mcp)
   - Control de Chrome real con sesión del usuario.
   - Tools: navigate, evaluate (JS), get_console_messages, get_network_requests,
     take_screenshot, click, type, etc.
   - Setup: requiere Chrome abierto con `--remote-debugging-port=9222`.

2. **`@supabase/mcp-server-supabase`** (https://github.com/supabase-community/supabase-mcp)
   - Acceso a Postgres + Auth + Storage del proyecto Supabase.
   - Por default `--read-only` para mitigar riesgo de mutaciones accidentales.
   - Tools: execute_sql, list_tables, list_storage_buckets, get_logs, etc.

Tier 2 (`github-mcp`, `sentry-mcp`, `better-stack-mcp`) y Tier 3
(`cloudflare-mcp`) quedan para fases posteriores cuando los servicios
correspondientes estén implementados (ver
`agent-self-validation-toolkit.md` §7).

## Alternativas evaluadas

### Alt 1: solo Playwright headless (status quo)
- Pros: 0 setup, ya funciona.
- Contras: NO ve la sesión del usuario (cookies, localStorage). No reproduce
  bugs que dependen de auth state. NO accede a DB sin pasar por API backend.
- Veredicto: insuficiente — bugs de auth requieren sesión real.

### Alt 2: `vercel-labs/agent-browser`
- Pros: browser semántico de alto nivel, bien para tasks tipo "completá un form".
- Contras: requiere cuenta Vercel + API key (costo). Menos enfocado a debugging
  técnico (devuelve descripción semántica, no console.log/network detallados).
- Veredicto: rechazada — para nuestro caso `chrome-devtools-mcp` es más directo
  y gratis.

### Alt 3: agregar más MCPs (sentry, better-stack, github) ahora
- Pros: cobertura completa.
- Contras: sentry/better-stack todavía no implementados (Sprint 2+); github
  útil cuando el repo esté pushed (aún local).
- Veredicto: diferido — sumamos en cuanto los servicios estén activos.

### Alt 4: build custom MCP propio del proyecto MT
- Pros: tools específicos al dominio (ej. `mt-pricing-recalculate`, `mt-comparator-trigger-poc`).
- Contras: trabajo adicional, mantenibilidad, redunda con tools existentes.
- Veredicto: rechazada Sprint 1; reconsiderar en Fase 2 si patterns repetitivos
  emergen.

## Consecuencias positivas

- **Reducción ~70-80%** de turnos en sesiones de debugging (estimado de la
  sesión 2026-05-07).
- **Validación end-to-end autónoma**: el agent puede confirmar que una feature
  funciona antes de marcar story done — login real + ver row en DB + ver UI
  renderizada — sin pedirle al usuario que confirme.
- **Audit trail mejorado**: queries DB y acciones browser quedan en logs Claude
  Code.
- **Onboarding nuevo dev más simple**: futuros devs en MT pueden usar el mismo
  toolkit para debugging asistido por AI.

## Consecuencias negativas / riesgos

- **Token management**: Supabase access token + GitHub PAT (futuro) deben
  rotarse trimestralmente. Si leak, comprometen TODOS los proyectos del usuario,
  no solo MT. Mitigación: tokens dedicados con scopes mínimos.
- **Surface de ejecución amplia**: el agent puede ejecutar SQL arbitrario contra
  prod si se desactiva `--read-only`. Mitigación: flag `--read-only` por default
  + audit log de queries.
- **Lock-in moderado**: si MT pivota a stack distinto (de Supabase a self-host
  Postgres, ej.), el supabase-mcp deja de aplicar. Mitigación: el toolkit no es
  arquitectural — solo accede al stack actual.
- **Curva de aprendizaje del usuario**: mantener `~/.claude.json` con MCPs
  configurados. Mitigación: scripts de setup + verify (`launch-chrome-debug.ps1`,
  `verify-mcp.ps1`) ya provistos.
- **Dependencia de Chrome corriendo**: chrome-devtools-mcp falla si el usuario
  cierra Chrome. Mitigación: Playwright headless como fallback siempre disponible.

## Cuándo revisar

- **Post-Sprint 3** (~T+6 sem): evaluar sumar `sentry-mcp` cuando esté
  implementado el observability stack (ADR-047).
- **Cierre Fase 1** (~T+3-4 meses): revisar uso real del toolkit, qué tools se
  usaron, cuáles no, y si vale sumar Tier 2-3.
- **Si Anthropic cambia el protocolo MCP** o aparece sucesor: revisar migración.

## Referencias

- `_bmad-output/planning-artifacts/agent-self-validation-toolkit.md` — catálogo
  detallado.
- `_bmad-output/planning-artifacts/agent-mcp-config.example.json` — config
  template para `~/.claude.json`.
- `infra/scripts/launch-chrome-debug.ps1` — script de arranque Chrome con remote
  debug.
- `infra/scripts/verify-mcp.ps1` — verificación pre-sesión del setup.
