# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This file is maintained automatically by `release-please` once the release
pipeline is enabled (Sprint 2). Hasta entonces se actualiza manualmente como
parte de cada PR significativo.

## [Unreleased]

### Added

- Initial monorepo scaffolding (Sprint 0 / Sprint 1 inception).
- Backend skeleton FastAPI + SQLAlchemy 2.0 async + Alembic.
- Frontend skeleton Next.js 16 + React 19 + Tailwind v4 + Shadcn UI.
- CI/CD GitHub Actions workflows (lint, typecheck, tests, build, deploy a staging).
- Docker Compose dev environment (api, worker, beat, redis, caddy, mailpit, grafana).
- Architecture v1.4 + 54 ADRs documented in
  `_bmad-output/planning-artifacts/` y resumidos en `docs/adr/README.md`.
- Documentos de proyecto: README, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT,
  CHANGELOG, LICENSE placeholder.
- Configs raíz: `.gitignore`, `.editorconfig`, `.nvmrc` (20),
  `.python-version` (3.11), `pnpm-workspace.yaml`, `package.json` (orchestration),
  `.commitlintrc.json`.
- Documentación operativa: `docs/architecture/`, `docs/adr/`, `docs/runbooks/`,
  `docs/onboarding/`, `docs/deployment/`.

### Changed

- (vacío)

### Deprecated

- (vacío)

### Removed

- (vacío)

### Fixed

- (vacío)

### Security

- (vacío)

---

[Unreleased]: https://github.com/<org>/br-mt-ecommerce/compare/v0.0.0...HEAD
