# Documentación — br-mt-ecommerce

Esta carpeta es el **índice operativo** de toda la documentación de la
plataforma MT Middle East. Los artefactos generados en discovery, planning y
arquitectura siguen viviendo en
[`_bmad-output/planning-artifacts/`](../_bmad-output/planning-artifacts/);
desde aquí los enlazamos y los complementamos con docs operacionales (runbooks,
onboarding, deployment).

---

## Estructura

| Carpeta | Contenido |
|---|---|
| [`architecture/`](./architecture/) | Arquitectura v1.4, diagrama C4 nivel 1 y links a documentos vivos |
| [`adr/`](./adr/) | Índice de los **54 ADRs** con status (proposed / accepted / superseded) |
| [`estrategia/`](./estrategia/) | Documentación de estrategia: guía de desarrollo del equipo, estrategia de requisitos y de pruebas |
| [`runbooks/`](./runbooks/) | RB-01 a RB-15 (placeholders, se completan en Sprint X+) |
| [`onboarding/`](./onboarding/) | Guía paso-a-paso para que un dev nuevo arranque local en < 15 min y mergee su primer PR en < 1 día |
| [`deployment/`](./deployment/) | CI/CD, releases, rollbacks (placeholder, link a `mt-cicd-pipeline.md`) |

---

## Documentos clave (atajos)

| Tema | Documento |
|---|---|
| Brief de producto | [`product-brief-mt-pricing-mdm-phase1.md`](../_bmad-output/planning-artifacts/product-brief-mt-pricing-mdm-phase1.md) |
| PRD Fase 1 | [`prd-mt-pricing-mdm-phase1.md`](../_bmad-output/planning-artifacts/prd-mt-pricing-mdm-phase1.md) |
| Arquitectura v1.4 | [`architecture-mt-pricing-mdm-phase1.md`](../_bmad-output/planning-artifacts/architecture-mt-pricing-mdm-phase1.md) |
| Sprint 0 plan | [`sprint0-plan-consolidado.md`](../_bmad-output/planning-artifacts/sprint0-plan-consolidado.md) |
| Sprint 1 backlog | [`sprint1-backlog-refined.md`](../_bmad-output/planning-artifacts/sprint1-backlog-refined.md) |
| Production readiness | [`production-readiness-master-plan.md`](../_bmad-output/planning-artifacts/production-readiness-master-plan.md) |
| Gap analysis | [`production-readiness-gap-analysis.md`](../_bmad-output/planning-artifacts/production-readiness-gap-analysis.md) |
| Risk register | [`risk-register-consolidado.md`](../_bmad-output/planning-artifacts/risk-register-consolidado.md) |
| OpenAPI contract | [`mt-api-contract-openapi.yaml`](../_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml) |
| Modelos SQLAlchemy | [`mt-sqlalchemy-models.md`](../_bmad-output/planning-artifacts/mt-sqlalchemy-models.md) |
| Frontend tech design | [`mt-frontend-tech-design.md`](../_bmad-output/planning-artifacts/mt-frontend-tech-design.md) |
| Jobs / Celery design | [`mt-jobs-module-design.md`](../_bmad-output/planning-artifacts/mt-jobs-module-design.md) |
| Users / RBAC design | [`mt-users-module-design.md`](../_bmad-output/planning-artifacts/mt-users-module-design.md) |
| KB module design | [`mt-kb-module-design.md`](../_bmad-output/planning-artifacts/mt-kb-module-design.md) |
| Product matching pipeline | [`mt-product-matching-pipeline-detail.md`](../_bmad-output/planning-artifacts/mt-product-matching-pipeline-detail.md) |
| CI/CD pipeline | [`mt-cicd-pipeline.md`](../_bmad-output/planning-artifacts/mt-cicd-pipeline.md) |
| Migrations + IaC + secrets | [`mt-migrations-iac-secrets-design.md`](../_bmad-output/planning-artifacts/mt-migrations-iac-secrets-design.md) |
| DR runbooks + SLA | [`mt-dr-runbooks-sla-design.md`](../_bmad-output/planning-artifacts/mt-dr-runbooks-sla-design.md) |
| Observability design | [`mt-observability-design.md`](../_bmad-output/planning-artifacts/mt-observability-design.md) |
| Security & compliance | [`mt-security-compliance-design.md`](../_bmad-output/planning-artifacts/mt-security-compliance-design.md) |
| UX mockups | [`ux-mockups-mt-pricing-mdm-phase1.md`](../_bmad-output/planning-artifacts/ux-mockups-mt-pricing-mdm-phase1.md) |

---

## Convenciones

- **Idioma**: prosa en español (LatAm/UAE neutral). Identificadores técnicos
  y código en inglés.
- **Markdown**: limpio, sin HTML salvo necesidad. Tablas legibles. Mermaid
  permitido.
- **Links**: relativos dentro del repo cuando sea posible.
- **Versionado de docs**: cualquier cambio significativo se trackea por PR.
  Documentos clave (PRD, Arquitectura) versionados con tag (`v1.0`, `v1.4`).
- **ADRs**: inmutables tras `accepted`. Si una decisión cambia, se crea un ADR
  nuevo que supersedea.
