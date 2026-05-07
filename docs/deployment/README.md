# Deployment

Documentación operativa de despliegue, releases y rollbacks.

> **Estado**: este README es un *placeholder*. La verdad de fondo vive en
> los siguientes documentos del directorio `_bmad-output/planning-artifacts/`,
> que se irán convirtiendo en runbooks ejecutables a lo largo de los
> sprints S2-S4.

---

## Documentos de referencia

| Tema | Documento |
|---|---|
| CI/CD pipeline (GitHub Actions) | [`mt-cicd-pipeline.md`](../../_bmad-output/planning-artifacts/mt-cicd-pipeline.md) |
| Migrations + IaC + secrets | [`mt-migrations-iac-secrets-design.md`](../../_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md) |
| DR runbooks + SLA | [`mt-dr-runbooks-sla-design.md`](../../_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md) |
| Observability design | [`mt-observability-design.md`](../../_bmad-output/planning-artifacts/mt-observability-design.md) |
| ADR-050 IaC Hetzner Terraform | [`ADR-050-iac-hetzner-terraform.md`](../../_bmad-output/planning-artifacts/adr/ADR-050-iac-hetzner-terraform.md) |
| ADR-051 Secrets Doppler | [`ADR-051-secrets-management-doppler.md`](../../_bmad-output/planning-artifacts/adr/ADR-051-secrets-management-doppler.md) |
| ADR-053 Backup & DR | [`ADR-053-backup-dr-strategy.md`](../../_bmad-output/planning-artifacts/adr/ADR-053-backup-dr-strategy.md) |

---

## Entornos

| Entorno | Propósito | Hosting | URL (placeholder) |
|---|---|---|---|
| `dev_local` | Desarrollo individual | Docker Compose en máquina del dev | `http://localhost:3000` |
| `staging` | Validación con MT (Paula) | Hetzner Cloud (UAE) | `https://staging.mt.<dominio>` |
| `prod` | Producción para MT | Hetzner Cloud (UAE) | `https://mt.<dominio>` |

Variables y secretos se gestionan con **Doppler** (proyecto `mt-pricing`).
Los stages Doppler reflejan los entornos: `dev_local`, `staging`, `prod`.

---

## Pipeline (resumen)

```
Push a feature branch
   └─► CI: lint + typecheck + tests + build (sin deploy)

Merge a main
   ├─► CI completo
   ├─► Build images Docker (api, worker, frontend)
   ├─► Push a registry
   └─► Deploy automático a staging (con migración alembic + healthcheck)

Tag vX.Y.Z (release-please) en main
   └─► Deploy manual aprobado a prod (canary 10% → 100% con rollback)
```

Detalles, jobs y matrices en
[`mt-cicd-pipeline.md`](../../_bmad-output/planning-artifacts/mt-cicd-pipeline.md).

---

## Releases

- **SemVer** estricto (`MAJOR.MINOR.PATCH`).
- **release-please** genera PRs de release a partir de Conventional Commits.
- `CHANGELOG.md` se mantiene automáticamente desde Sprint 2.
- Tag git `vX.Y.Z` dispara el deploy a producción (manual approve).

---

## Rollback

Política: **rollback rápido** preferido sobre "fix-forward" cuando hay
incidente en producción.

Pasos resumidos (detalle en RB-12):

1. Revertir deploy: redeploy de la imagen anterior (vía CD pipeline o
   manualmente con `docker compose pull && up`).
2. Si la migración fue destructiva: ejecutar `alembic downgrade -1` **solo si
   el ADR-049 (expand-contract) se respetó** y la migración previa es segura.
   En caso contrario, restaurar desde backup (ver RB-01).
3. Verificar healthchecks y error budget.
4. Comunicar a stakeholders.
5. Post-mortem obligatorio.

---

## TODOs operativos

- [ ] Subir el primer pipeline GitHub Actions (S1/S2).
- [ ] Configurar Doppler `staging` y `prod` con todos los secretos.
- [ ] Provisionar Hetzner staging vía Terraform (S2).
- [ ] Documentar zone DNS y certificados (S2).
- [ ] Escribir RB-12 (release y rollback) con comandos copy-paste (S2).
- [ ] Definir y documentar política de canary deploys con observabilidad
  acoplada al error budget (S3).
