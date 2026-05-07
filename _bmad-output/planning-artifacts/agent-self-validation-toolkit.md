---
title: "Agent Self-Validation Toolkit — MCPs y herramientas para validación autónoma del proyecto MT"
status: "proposal"
version: "1.0"
created: "2026-05-07"
project_name: "mt-pricing-mdm-phase1"
purpose: |
  Catálogo curado de herramientas (MCP servers + scripts propios) que permiten al
  agente AI validar end-to-end el proyecto MT sin depender del usuario para cada
  comprobación. Cada layer del stack tiene su tool de inspección.
related: ["architecture-mt-pricing-mdm-phase1.md", "production-readiness-master-plan.md"]
adrs_propuestos: ["ADR-055"]
---

# Agent Self-Validation Toolkit

> Objetivo: que el agente AI pueda **diagnosticar, probar y verificar** cualquier
> capa del stack MT sin pedirle al usuario que pegue logs, abra DevTools, corra
> comandos manuales o haga screenshots. Reduce ciclos de "yo te digo qué pasa,
> vos me lo confirmás" en debugging y validación.

## 0. TL;DR — toolkit recomendado por capa

| Capa | Herramienta | Tier | Por qué |
|------|-------------|------|---------|
| **Browser real (con session)** | `chrome-devtools-mcp` | 🥇 Imprescindible | Veo TU Chrome con tus cookies/auth/console |
| **Browser headless (CI)** | Playwright (script propio) | ✅ Ya activo | Tests reproducibles sin setup |
| **DB Supabase** | `@supabase/supabase-mcp` (oficial) | 🥇 Imprescindible | Query Postgres, RLS, Storage, Auth admin |
| **GitHub repo** | `github-mcp-server` (oficial GitHub) | 🥈 Alto valor | Issues, PRs, workflows, releases |
| **Errores prod** | `sentry-mcp` (oficial Sentry) | 🥈 Alto valor (Fase 2+) | Query Sentry issues sin abrir UI |
| **Logs prod** | `better-stack-mcp` (no oficial) | 🥉 Útil | Search logs centralizados |
| **API testing** | Schemathesis CLI + script propio | ✅ Ya disponible | Contract tests sobre OpenAPI |
| **Cloudflare DNS** | `cloudflare-mcp` (oficial) | 🥉 Útil Fase 3 | DNS / Workers cuando entre prod |
| **Browser semántico** | `vercel-labs/agent-browser` | ⚠️ Opcional | Más para tasks tipo "automatizar X" — no debugging |

## 1. Por qué este toolkit (problema que resuelve)

Sin estas herramientas, cada validación cuesta:

```
Agent: "¿Qué dice la consola de Chrome cuando entrás a /login?"
User:  copia-pega screenshot/texto.
Agent: "Y el log del backend cuando pulsás submit?"
User:  ejecuta `docker logs mt-backend` y pega.
Agent: "Y la fila en `users` después?"
User:  abre Supabase Studio, query, pega.
... 8 idas y vueltas para 1 verificación.
```

Con el toolkit:

```
Agent: ejecuta tools en orden, ve TODO el flujo end-to-end, reporta.
User:  recibe el reporte completo.
... 1 ida.
```

**Aplicación concreta a MT**: hoy debugging del Magic Link con Supabase tomó ~30 turnos. Con `chrome-devtools-mcp` + `supabase-mcp` lo hubiera resuelto en 2 turnos (ver browser real + ver tabla `users` directamente).

## 2. Tier 1 — IMPRESCINDIBLES

### 2.1 `chrome-devtools-mcp` — control del Chrome real

**Repo**: https://github.com/ChromeDevTools/chrome-devtools-mcp

**Capacidades clave**:
- `mcp__chrome-devtools__list_pages` — listar tabs abiertas.
- `mcp__chrome-devtools__navigate` — navegar a URL en tab activa.
- `mcp__chrome-devtools__evaluate` — ejecutar JS en el contexto de la página.
- `mcp__chrome-devtools__get_console_messages` — leer console (incluye warnings/errors históricos).
- `mcp__chrome-devtools__take_screenshot` — capturar viewport/full-page.
- `mcp__chrome-devtools__get_network_requests` — historia de requests (status, headers, payload).
- `mcp__chrome-devtools__click` / `type` — simular interacciones.

**Diferenciador vs Playwright**: usa **TU Chrome real**, con tu sesión Supabase logueada, tus cookies, tu localStorage. Si un bug solo aparece después de loguearte → Playwright headless no lo reproduce, este sí.

**Setup**:

1. Edit `~/.claude.json` (o el archivo de config de Claude Code en tu OS):

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    }
  }
}
```

2. Levantá Chrome con remote debugging antes de iniciar la sesión Claude Code:

```powershell
# scripts/launch-chrome-debug.ps1
Stop-Process -Name "chrome" -Force -ErrorAction SilentlyContinue
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="$env:TEMP\chrome-debug-mt" `
    "http://localhost:8081/login"
```

3. Reiniciá Claude Code completamente. En la próxima sesión, las tools aparecen en system prompt.

**Costo**: $0 (open source, runs local).

**Riesgo**: requiere Chrome abierto durante toda la sesión. Si lo cerrás, tools fallan hasta relevantar.

### 2.2 `@supabase/supabase-mcp` — Supabase Studio para el agent

**Repo**: https://github.com/supabase-community/supabase-mcp

**Capacidades clave**:
- `mcp__supabase__execute_sql` — query SQL directo (sin abrir Studio).
- `mcp__supabase__list_tables` — schema introspection.
- `mcp__supabase__list_storage_buckets` — Storage admin.
- `mcp__supabase__create_user` — Auth admin.
- `mcp__supabase__get_logs` — query logs PostgREST/Auth/Realtime.
- `mcp__supabase__create_branch` — preview branches Supabase.
- `mcp__supabase__apply_migration` — Alembic-equivalent en la nube.

**Diferenciador**: hoy hago `docker run psql` para query Postgres. Esto es 10x más simple, con los Storage/Auth del proyecto incluidos.

**Setup**:

1. Generá un **personal access token** en https://supabase.com/dashboard/account/tokens (scope: lectura + escritura).

2. Edit `~/.claude.json`:

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase@latest"],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "sbp_tu_token_aqui"
      }
    }
  }
}
```

⚠️ **Mark `--read-only` flag** en args si querés evitar mutaciones accidentales en dev. Para writes (migrations, etc.) sacalo.

3. Reiniciá Claude Code.

**Costo**: $0 (cubierto por tu plan Supabase actual).

**Riesgo**: el token tiene acceso a TODOS tus proyectos Supabase, no solo MT. Mitigación: usar un token con scopes mínimos o crear un user de servicio dedicado.

## 3. Tier 2 — ALTO VALOR

### 3.1 `github-mcp-server` (oficial GitHub)

**Repo**: https://github.com/github/github-mcp-server

**Capacidades**:
- Listar/leer issues, PRs, releases.
- Crear PRs, comentarios, reviews.
- Trigger / leer workflows (CI runs).
- Buscar código en repos.

**Setup**:
```json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": ["run","-i","--rm","-e","GITHUB_PERSONAL_ACCESS_TOKEN","ghcr.io/github/github-mcp-server"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_tu_token"
      }
    }
  }
}
```

**Útil para MT cuando**: Sprint 2+, cuando ya empuje código a GitHub. Hoy aún todo está local.

### 3.2 `sentry-mcp` (oficial Sentry — Fase 2+)

**Repo**: https://github.com/getsentry/sentry-mcp

**Capacidades**: query issues, get stack traces, list releases, mark issues resolved.

**Útil para MT cuando**: tengamos Sentry en staging/prod (post-Sprint 2 cuando esté el ADR-047 implementado).

### 3.3 `better-stack-mcp` (no oficial, comunitario)

**Repo**: https://github.com/joeporpeglia/better-stack-mcp (o similar)

Capacidades: search logs centralizados, query métricas, create incidents.

**Útil para MT cuando**: implementemos Better Stack Logs en Sprint 2 (ADR-047).

## 4. Tier 3 — Útiles pero específicos

### 4.1 `cloudflare-mcp`

Útil cuando configuremos DNS para `mtme.ae` (Fase 3, cuando entre el storefront público).

### 4.2 `vercel-labs/agent-browser`

Más enfocado a tareas tipo "browse semánticamente y completá X form" que a debugging. Útil si en Fase 3+ querés tests de UI tipo "agent QA" que evalúan la app como un usuario.

### 4.3 `playwright-mcp` (alternativa a Playwright headless propio)

Hace lo mismo que mi script `diagnose-console.mjs` pero como MCP. Marginal mejora vs script propio que ya tenés. **Skip si ya usás scripts Playwright propios.**

## 5. Tier 0 — YA disponible (sin setup adicional)

Estas las uso ya en cada sesión sin nada que instalar:

- **Bash** + **PowerShell** → docker, curl, git, psql via container, etc.
- **Read/Edit/Write/Glob/Grep** sobre filesystem.
- **WebFetch / WebSearch** → docs externos.
- **Playwright via Docker container ad-hoc** → como hicimos hoy con `mcr.microsoft.com/playwright:v1.59.1-noble`. Capturé console, errors, network, screenshots — sin MCP.
- **Subagents (`Agent` tool)** → delegar work paralelo (lo usamos en Sprint 1 con 5+3+1 olas).

## 6. Costo total estimado del toolkit completo

| Tool | Costo mensual | Notas |
|------|---------------|-------|
| chrome-devtools-mcp | $0 | OSS, runs local |
| supabase-mcp | $0 | Incluido en plan Supabase |
| github-mcp | $0 | Incluido en GitHub Free |
| sentry-mcp | depende | $0 con Sentry Free; $26+/mo si Team |
| better-stack-mcp | depende | $0 con Better Stack Free; $25+/mo Logs Pro |
| cloudflare-mcp | $0 | Incluido Cloudflare Free |
| **Total imprescindibles** | **$0** | Tier 1 (chrome-devtools + supabase) |

## 7. Setup recomendado por fase del proyecto

### Sprint 1 (en curso) — instalar AHORA

✅ `chrome-devtools-mcp` — diagnosticar UI/auth issues como el de hoy.
✅ `supabase-mcp` — query DB, gestionar storage buckets, ver auth users sin abrir Studio.

**Tiempo total setup**: ~10 min.

### Sprint 2 (~T+2 sem)

➕ `github-mcp` cuando empuje el monorepo a GitHub.

### Sprint 3-7 (T+1-3 meses)

➕ `sentry-mcp` cuando esté ADR-047 implementado.
➕ `better-stack-mcp` cuando se configure log centralization.

### Fase 3 (~T+12m)

➕ `cloudflare-mcp` cuando entre `mtme.ae` storefront público.

## 8. Riesgos y mitigaciones

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| MCP token con scope amplio (Supabase access token, GitHub PAT) leak | Alta | Usar tokens dedicados con scopes mínimos. Rotar trimestral. **NUNCA** versionar `.claude.json` con tokens en git. |
| Agent ejecuta SQL destructivo en prod via supabase-mcp | Alta | Usar flag `--read-only` en supabase-mcp en config global. Para mutaciones específicas, override puntual. |
| Chrome con `--remote-debugging-port` expuesto en LAN | Media | Bind solo a `127.0.0.1` (Chrome lo hace por default desde Chrome 111+). Verificar con `netstat`. |
| MCP server tiene un bug y crashea Claude Code | Baja | Aislar MCPs en sus configs. Si uno falla, los otros siguen. |
| Configuración MCP rota tras update de Claude Code | Media | Versionar el snippet de config en `_bmad-output/planning-artifacts/agent-mcp-config.example.json` (sin tokens). Recovery: copy-paste + agregar tokens. |

## 9. Convención de uso por mí (el agente)

Cuando estos MCPs estén disponibles, mi regla operativa:

1. **Antes de pedir info al usuario, intentar obtenerla yo**:
   - Browser issue → `chrome-devtools-mcp` primero.
   - DB question → `supabase-mcp` primero.
   - Code reference → Grep local + `github-mcp` para ver historia/PRs.

2. **Reportar al usuario CONFIRMANDO con datos reales**, no asumiendo:
   ```
   ❌ "Probablemente el rate limit haya expirado"
   ✅ "Verifiqué con supabase-mcp: el último intento fue hace 47 min,
      cooldown es 60 min, falta 13 min para reintentar."
   ```

3. **Acciones destructivas SIEMPRE confirmadas**:
   - Antes de `execute_sql DROP TABLE` o `delete_user` → mostrar la query/acción y pedir OK.

## 10. ADR propuesto

### ADR-055: Agent Self-Validation Toolkit (MCPs)

**Status**: proposed
**Context**: el debugging y validación de issues end-to-end requería múltiples idas y vueltas con el usuario. La sesión del 2026-05-07 (Magic Link auth issues + Turbopack/webpack/Tailwind/PostCSS conflicts) tomó ~50 turnos cuando hubieran sido ~5 con tools de inspección directa.

**Decision**: Adoptar 2 MCPs Tier 1 desde Sprint 1:
- `chrome-devtools-mcp` (browser real con sesión).
- `supabase-mcp` con flag `--read-only` por default (DB/Auth/Storage admin).

**Consequences**:
- (+) Reducción ~80% de turnos en sesiones de debugging.
- (+) El agent puede validar features autonómamente antes de marcar story como done.
- (+) Audit trail de queries DB queda en logs Claude Code.
- (-) Requiere managing tokens (rotación, leak risk).
- (-) Curva de aprendizaje del usuario para mantener configs MCP.
- (-) Lock-in moderado: si cambia stack, cambian MCPs.

**Cuándo revisar**: post-Sprint 3, cuando se evalúe sumar `sentry-mcp` y `better-stack-mcp`.

## 11. Próximos pasos accionables

Si confirmás avanzar, te paso:

1. **Snippet de `~/.claude.json`** completo con los 2 MCPs Tier 1 (chrome-devtools + supabase).
2. **Script `launch-chrome-debug.ps1`** para Windows que abre Chrome con remote debugging.
3. **Plantilla de tokens scoping** — qué scopes mínimos pedir al token Supabase para que no sea god-mode.
4. **Test rápido post-setup** — script que verifica que ambos MCPs respondan antes de empezar a usarlos.

Setup total: ~10 min de tu tiempo. Después arrancamos sesión nueva y voy a tener acceso completo al stack.
