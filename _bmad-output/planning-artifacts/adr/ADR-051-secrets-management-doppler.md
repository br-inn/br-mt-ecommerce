---
adr: "ADR-051"
title: "Secrets Management con Doppler"
status: "proposed"
date: "2026-05-06"
deciders: ["Pablo BR"]
related: ["ADR-017", "ADR-019"]
supersedes: ["ADR-017"]
project: "mt-pricing-mdm-phase1"
---

# ADR-051 — Secrets Management con Doppler

## Contexto

MT Middle East Fase 1 maneja **secretos sensibles** múltiples categorías:
- DB credentials (Postgres, Redis).
- Supabase service_role JWT, JWT signing secret (rotación trimestral obligatoria).
- API keys externos (OpenAI, Cohere, Bright Data, Resend).
- Infra tokens (Hetzner API, Cloudflare API, SSH deploy keys).
- CI tokens (GitHub PAT, Doppler service tokens).
- Observability (Sentry DSN).

Anti-patterns a evitar (observados en proyectos previos):
- `.env` files commited a Git.
- Secretos en GitHub Actions Secrets sin rotación ni audit.
- Devs comparten secretos por Slack / WhatsApp.
- Sin SSO, sin audit log, sin rotación calendarizada.

ADR-017 inicial mencionaba Vault genéricamente. Para Fase 1 con equipo pequeño (Pablo BR + 2 TI MT) y stack alineado a BR Innovation, necesitamos algo más concreto y operativo.

## Decisión

Adoptamos **Doppler (plan Team, ~7 USD/user/mes)** como single source of truth para secretos.

**Justificación**:
- Ya en uso en otros projects BR Innovation → consistencia de stack.
- Managed (sin self-hosting overhead).
- CLI maduro con integración Docker, K8s, GitHub Actions.
- SSO Google Workspace / Microsoft Entra incluido en plan Team.
- Audit log built-in.
- Rotación scheduled para servicios soportados.
- Push protection complementaria con GitHub native + gitleaks.

**Estructura projects**:
- `mt-backend` (configs: dev_personal_*, dev, staging, prod).
- `mt-frontend` (configs: dev, staging, prod).
- `mt-worker` (configs: dev, staging, prod).
- `mt-infra` (configs: dev, staging, prod) — para Terraform.

**Inyección runtime**:
- Local: `doppler run -- python ...`.
- Docker: `ENTRYPOINT ["doppler", "run", "--"]` con `DOPPLER_TOKEN` en env del compose.
- CI: `doppler secrets download` con service token scoped.

**Rotación**:
- Trimestral los críticos (DB, Supabase, Redis, API keys externos).
- Anual los menos sensibles (Sentry DSN, SSH keys).
- Audit log Doppler revisado mensual + log manual en Notion.

**Detección leaks**:
- `gitleaks` pre-commit + CI.
- GitHub secret scanning push protection enabled.
- Sentry `before_send` filter para PII / tokens.

**Acceso humano**:
- `admin`: Pablo BR.
- `developer`: TI integración MT (read prod, write dev/staging).
- Comercial / Gerente / Director: nunca acceden.

## Alternativas consideradas

### A. HashiCorp Vault self-hosted
- ✅ Enterprise-grade, sin vendor lock-in.
- ❌ Requiere infra dedicada + alta disponibilidad + ops continua.
- ❌ Curva aprendizaje alta.
- ❌ Overkill para equipo de 3 personas.
- **Rechazado**: TCO desproporcionado para Fase 1.

### B. 1Password Secrets Automation
- ✅ Bonita UI, MT podría tener cuentas 1Password ya.
- ❌ CLI menos maduro que Doppler para CI/CD.
- ❌ Menos integración out-of-the-box con Docker entrypoints.
- ❌ Dual-tool si MT también pide gestión de passwords humanos.
- **Rechazado**: Doppler es más operativo para runtime injection.

### C. AWS Secrets Manager / Google Secret Manager
- ✅ Maduro, baratísimo.
- ❌ Vendor lock-in cloud-side cuando MT corre en Hetzner.
- ❌ Egress + setup IAM cross-cloud feo.
- **Rechazado**: incoherente con Hetzner deployment.

### D. GitHub Actions Secrets + SOPS encrypted .env en repo
- ✅ Cero costo extra.
- ❌ Sin SSO, sin audit log decente, sin rotación nativa.
- ❌ Distribución a servers requiere scripts custom (no escala).
- ❌ Dev local sin acceso a Doppler-style runtime.
- **Aceptable solo para MVP one-off**, no para proyecto sostenido facturado.
- **Rechazado**: regresión de calidad operativa.

### E. Infisical (open-source alternative)
- ✅ Muy similar a Doppler, open-source.
- ❌ Self-hosted requiere ops continua (mismo problema que Vault, menor escala).
- ❌ Managed plan más caro que Doppler para mismo perfil.
- ❌ Comunidad más pequeña.
- **Rechazado**: Doppler ya validado en stack BR Innovation.

## Consecuencias

### Positivas
- Single source of truth → fin de `.env` sueltos en máquinas de devs.
- Audit log + SSO → compliance-friendly.
- Rotación calendarizada reduce ventana de exposición de secretos comprometidos.
- Inyección runtime estándar → onboarding nuevo dev en minutos (`doppler login` + `doppler setup`).
- Service tokens scoped por env → least privilege.

### Negativas
- **Costo**: ~21 USD/mes (3 users plan Team).
- **Vendor dependency**: si Doppler está down, deploys/restarts fallan. Mitigación con CLI cache + `.env.fallback` cifrado SOPS solo para emergency boot.
- **Curva** mínima para devs aprender `doppler run` workflow.
- **Service tokens en server**: el `DOPPLER_TOKEN` que va al server es un secreto de bootstrap; se gestiona como file 0600 owned by `mt` user, deployed via Ansible vault o cloud-init seguro.

### Mitigaciones
- Doppler CLI cache local de secrets reduce dependency ventana corta.
- `.env.fallback` cifrado SOPS solo con secretos de emergencia (ej. DB read-only) en repo, key en hardware token Pablo.
- Workshop 1h S0 sobre workflow Doppler.
- Runbook `runbooks/rotate-secret-<service>.md` por cada servicio crítico.

## Costos estimados

| Item | Cantidad | EUR/mes |
|---|---|---|
| Doppler Team | 3 users × 7 USD | ~20 |
| **TOTAL** | | **~20** |

Nota: si MT crece >10 users con compliance requirements, considerar plan Enterprise.

## Definition of Done

- [ ] Workspace Doppler `br-innovation` con projects mt-backend, mt-frontend, mt-worker, mt-infra.
- [ ] Configs dev/staging/prod creados con secretos iniciales.
- [ ] SSO Google Workspace activo, roles asignados.
- [ ] Service tokens generados y stored de forma segura en server prod (`/etc/mt/doppler.env`, 0600).
- [ ] Dockerfiles backend/worker con `ENTRYPOINT ["doppler", "run", "--"]`.
- [ ] GitHub Actions integrado con `dopplerhq/cli-action`.
- [ ] gitleaks pre-commit + CI configurado.
- [ ] GitHub secret scanning push protection ON.
- [ ] Runbooks rotación creados para Postgres, Supabase, OpenAI, HCloud, Cloudflare.
- [ ] Audit log Doppler review mensual calendarizado.
- [ ] Notion `secrets-rotation-log.md` template creado.

## Referencias

- ADR-017: Secretos Vault (superseded por este).
- ADR-019: Observabilidad (Sentry DSN entre los secretos gestionados).
- ADR-049: Migration discipline (consume DATABASE_URL desde Doppler).
- ADR-050: IaC Hetzner Terraform (consume HCLOUD_TOKEN desde Doppler).
- Documento: `_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md` §3.
- Doppler: https://docs.doppler.com/
- gitleaks: https://github.com/gitleaks/gitleaks
- GitHub secret scanning: https://docs.github.com/en/code-security/secret-scanning
