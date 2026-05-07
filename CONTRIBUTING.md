# Guía de contribución — br-mt-ecommerce

> **Filosofía**: BR Innovation desarrolla esta plataforma para MT Middle East
> en single-tenant. Calidad, auditabilidad y mantenibilidad están por encima
> de la velocidad. Cada PR debe poder defenderse ante una auditoría externa.

---

## 1. Workflow de branches y PRs

1. Toda feature parte de una **rama nueva** desde `main`:
   - `feat/<scope>-<descripcion-corta>`
   - `fix/<scope>-<descripcion-corta>`
   - `chore/<descripcion>`
   - `docs/<descripcion>`
   - Ejemplo: `feat/pricing-engine-canal-rules`, `fix/auth-rls-policies`.
2. Commits siguiendo **Conventional Commits** (ver §2).
3. Push y abrir **Pull Request** contra `main` con:
   - Título conciso (≤ 100 caracteres).
   - Descripción con: contexto, qué cambia, cómo se probó, riesgos, referencias
     a ADR o issue.
4. CI verde obligatorio (lint + typecheck + tests + build).
5. **≥ 1 approval** de otro contribuidor con permisos.
6. Merge **squash** (default) salvo casos justificados (release branches).
7. Nunca hacer push directo a `main` ni `--force` salvo emergencia documentada
   en post-mortem.

### Ramas protegidas

- `main`: producción de planning + verdad. Protegida (PR + CI + 1 approval).
- `release/*`: ramas de release-please. No tocar manualmente.

---

## 2. Conventional Commits

Formato: `<type>(<scope>): <subject>`

Tipos permitidos:

| Tipo | Uso |
|---|---|
| `feat` | Nueva funcionalidad para el usuario |
| `fix` | Corrección de bug |
| `chore` | Tareas de mantenimiento sin cambio funcional (deps, configs) |
| `docs` | Solo documentación |
| `refactor` | Cambio de código sin alterar comportamiento |
| `test` | Añadir o corregir tests |
| `style` | Formato (no afecta lógica) |
| `perf` | Mejora de rendimiento |
| `build` | Cambios en sistema de build / dependencias compiladas |
| `ci` | Cambios en pipelines CI |
| `revert` | Reversión de un commit anterior |

Ejemplos:

```
feat(pricing): añadir motor de reglas por canal con expand-contract
fix(auth): corregir RLS en supabase para rol approver
docs(adr): añadir ADR-055 para feature flags
refactor(catalog): extraer lógica de matching a servicio dedicado
test(comparator): cubrir caso edge de OCR fallback
```

Validación automática vía `commitlint` (ver `.commitlintrc.json`) en hook
`commit-msg` (Husky).

---

## 3. Estándares de código

### Backend (Python)

- **Formato**: `ruff format` (configurado en `pyproject.toml`).
- **Lint**: `ruff check` con reglas estrictas (incluye E, F, W, I, B, UP, S, BLE).
- **Type checking**: `mypy --strict`. Cero `Any` salvo justificación en comentario.
- **Tests**: `pytest` con cobertura mínima **70 %** global; **90 %** en
  `app/services/pricing_engine/`, `app/services/comparator/` y cualquier
  módulo que emita `audit_events`.
- **Async first**: SQLAlchemy 2.0 async, `httpx` async, no mezclar sync.
- **Imports**: ordenados con isort (a través de ruff).

Comandos:

```bash
cd mt-pricing-backend
uv run ruff check .
uv run ruff format .
uv run mypy app
uv run pytest --cov=app --cov-report=term-missing
```

### Frontend (TypeScript)

- **Formato**: Prettier (configurado en `mt-pricing-frontend/`).
- **Lint**: ESLint con preset Next.js + reglas TypeScript strict.
- **Type checking**: `tsc --noEmit`, `strict: true`.
- **Tests**: Vitest (unit + componentes), Playwright (E2E críticos).
- **Componentes UI**: Shadcn UI; nuevos componentes via CLI Shadcn.
- **i18n**: todas las strings visibles vía `next-intl`. Cero hardcode en JSX.
- **Accesibilidad**: WCAG AA en formularios y flujos críticos.

Comandos:

```bash
cd mt-pricing-frontend
pnpm lint
pnpm typecheck
pnpm test
pnpm test:e2e
```

---

## 4. Tests y cobertura

| Módulo | Cobertura mínima |
|---|---|
| Backend global | 70 % |
| `pricing_engine/` | 90 % |
| `comparator/` | 90 % |
| Endpoints que emiten audit_events | 90 % |
| Frontend global | 70 % |
| Componentes críticos (forms approve, comparator UI) | 85 % |

Tests de integración con Postgres real (testcontainers) son obligatorios para
cualquier feature que toque migraciones, RLS o jobs Celery.

---

## 5. ADRs — Architecture Decision Records

**Cualquier decisión arquitectural significativa requiere un ADR.** Ejemplos:

- Adopción de una nueva dependencia mayor.
- Cambio de patrón de persistencia, auth, jobs, observability.
- Cambio de formato de API pública.
- Política nueva de seguridad / compliance.

### Cómo crear un ADR

1. Copiar plantilla:
   ```bash
   cp _bmad-output/planning-artifacts/adr/ADR-001-stack-tecnologico.md \
      _bmad-output/planning-artifacts/adr/ADR-0XX-<slug>.md
   ```
2. Numerar correlativo (siguiente disponible — ver `docs/adr/README.md`).
3. Llenar secciones: Contexto, Decisión, Consecuencias, Alternativas
   consideradas, Status (`proposed`).
4. Abrir PR con label `adr`.
5. Tras aceptación: status pasa a `accepted` y se actualiza
   [`docs/adr/README.md`](./docs/adr/README.md).
6. Si supersedea otro ADR: marcar el anterior como `superseded by ADR-0XX`.

---

## 6. Migraciones de base de datos

Política obligatoria: **expand-contract**. Nunca breaking changes en un solo paso.

1. **Expand**: añadir nuevas columnas/tablas/índices manteniendo compatibilidad.
2. Deploy backend que lee viejo + nuevo.
3. **Backfill** con job idempotente.
4. Deploy backend que lee solo nuevo.
5. **Contract**: dropear lo viejo en PR separado.

Reglas duras:

- Prohibido `DROP COLUMN`, `DROP TABLE`, `ALTER COLUMN TYPE` destructivo en `main`
  sin aprobación explícita y plan de rollback documentado.
- Cada migración Alembic debe incluir `downgrade()` funcional.
- Migraciones revisadas por al menos un reviewer con context de DB.

### Crear una nueva migración Alembic

```bash
cd mt-pricing-backend
uv run alembic revision --autogenerate -m "feat: añadir tabla price_rules"
# Editar el archivo generado en alembic/versions/ — autogenerate no es perfecto
uv run alembic upgrade head    # aplicar local
uv run alembic downgrade -1    # verificar rollback
```

Ver [ADR-049](./_bmad-output/planning-artifacts/adr/ADR-049-migration-discipline.md).

---

## 7. Code review checklist

Para cada PR, el reviewer verifica:

- [ ] **Auditabilidad**: cambios sensibles emiten `audit_events` con actor, antes/después, IP, timestamp.
- [ ] **RLS**: cualquier nueva tabla con datos de tenant tiene políticas RLS aplicadas y testeadas.
- [ ] **Permisos**: endpoints chequean rol vía dependencia FastAPI; frontend oculta UI según rol.
- [ ] **Observability**: logs estructurados (JSON) + métricas Prometheus + traces OTel donde aplique.
- [ ] **i18n**: strings visibles en `messages/` (es + en) — no hardcode.
- [ ] **Accesibilidad**: labels, contraste, navegación teclado en formularios.
- [ ] **Performance**: queries N+1 evitadas; índices DB justificados; paginación en listados.
- [ ] **Seguridad**: no secretos en código; inputs validados con Pydantic/Zod; output sanitizado.
- [ ] **Tests**: cobertura cumplida; tests de happy path + error path + edge cases.
- [ ] **Migraciones**: expand-contract; downgrade verificado.
- [ ] **Documentación**: README, ADR o runbook actualizado si aplica.
- [ ] **Conventional Commits**: cumplidos.

---

## 8. Cómo agregar...

### ...un endpoint API

1. Definir el contrato en `_bmad-output/planning-artifacts/mt-api-contract-openapi.yaml`.
2. Crear schema Pydantic en `mt-pricing-backend/app/schemas/<modulo>.py`.
3. Crear router en `app/api/v1/<modulo>.py` con permisos vía `Depends`.
4. Implementar service en `app/services/<modulo>/`.
5. Tests: unitario (service) + integración (endpoint con DB testcontainer).
6. Cliente tipado en frontend (regenerar con `pnpm gen:api` si está configurado).
7. Emitir `audit_event` si la acción es sensible.

### ...un componente Shadcn

```bash
cd mt-pricing-frontend
pnpm dlx shadcn@latest add <componente>     # ej: data-table, form, dialog
```

Componentes propios viven en `components/`; los Shadcn raw en `components/ui/`.
Cualquier override sustancial requiere comentario explicando el motivo.

### ...una migración (ver §6).

### ...un ADR (ver §5).

---

## 9. Hooks y herramientas locales

### 9.1 Setup inicial (una sola vez tras `git clone`)

```bash
# 1. Instalar dependencias Node del workspace raíz (commitlint, husky, lint-staged)
pnpm install

# 2. Instalar el framework pre-commit (Python). Recomendado en venv dedicado o pipx.
pip install --user pre-commit          # o: pipx install pre-commit

# 3. Activar todos los hooks (pre-commit + commit-msg)
pnpm run hooks:install
# Equivale a:
#   pre-commit install
#   pre-commit install --hook-type commit-msg

# 4. (Opcional pero recomendado) Correr todos los hooks contra el repo entero.
#    La PRIMERA ejecución descarga las herramientas (ruff, mypy, prettier, gitleaks…)
#    y puede tardar 2–5 minutos. Las siguientes son <10 s.
pnpm run hooks:run
# Equivale a: pre-commit run --all-files
```

### 9.2 Qué hace cada hook (definido en `.pre-commit-config.yaml`)

| Hook | Stage | Qué valida |
|---|---|---|
| `check-yaml`, `check-json`, `check-toml` | pre-commit | Sintaxis de configs |
| `check-merge-conflict`, `check-case-conflict` | pre-commit | Merge markers, name clashes |
| `check-added-large-files` (≤10 MB) | pre-commit | Bloqueo de binarios grandes |
| `end-of-file-fixer`, `trailing-whitespace`, `mixed-line-ending` (LF) | pre-commit | Higiene de archivos |
| `ruff` (`--fix`) + `ruff-format` | pre-commit | Lint y formato Python (backend) |
| `mypy` | pre-commit | Type checking selectivo en `app/` |
| `prettier` | pre-commit | Formato de TS/JS/JSON/MD/YAML del frontend |
| `frontend-eslint` (local) | pre-commit | `pnpm --filter mt-pricing-frontend lint` |
| `frontend-typecheck` (local) | pre-commit | `pnpm --filter mt-pricing-frontend typecheck` |
| `gitleaks` | pre-commit | Detección de secretos (API keys, tokens) |
| `shellcheck` | pre-commit | Lint de scripts `.sh` |
| `yamllint` (relaxed) | pre-commit | Lint suave de YAML |
| `commitizen` | commit-msg | Conventional Commits (mensaje) |

> Workflow CI complementario: `.github/workflows/secrets-scan.yml` corre
> `gitleaks` + `trufflehog` también en GitHub Actions, defensa en profundidad.

### 9.3 Comandos útiles

```bash
# Correr hooks solo sobre archivos staged
pre-commit run

# Correr un hook concreto
pre-commit run ruff --all-files
pre-commit run gitleaks --all-files

# Actualizar versiones de los hooks (revisar el diff antes de commitear)
pre-commit autoupdate

# Saltar hooks SOLO en emergencia (requiere justificación en el PR)
git commit --no-verify -m "..."
```

### 9.4 Equivalente a través de scripts pnpm (no requieren instalar pre-commit)

Útil cuando un colaborador no quiere instalar Python/pre-commit:

```bash
pnpm run lint          # frontend + backend (ruff + eslint)
pnpm run typecheck     # frontend (tsc) + backend (mypy)
pnpm run test          # frontend (vitest) + backend (pytest)
pnpm run lint:backend  # solo backend (ruff)
pnpm run lint:frontend # solo frontend (eslint)
```

### 9.5 Reglas de oro

- Si un hook falla: **arreglar el problema y crear un commit nuevo**. NUNCA
  amend con cambios mayores ni `--no-verify` sin justificación documentada en el PR.
- `commitlint` valida `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`,
  `style:`, `perf:`, `build:`, `ci:`, `revert:`. Cualquier otro tipo es rechazado.
- Los hooks son **idempotentes**: correrlos dos veces sobre el mismo árbol no
  produce cambios. Si lo hacen, es bug del hook (reportar).

---

## 10. Soporte y contacto

- **Tech lead**: Pablo Sierra — `psierra@br-innovation.com`.
- **Canal de discusión**: Slack #mt-platform (interno BR/MT).
- **Reportar vulnerabilidades**: ver [`SECURITY.md`](./SECURITY.md).
