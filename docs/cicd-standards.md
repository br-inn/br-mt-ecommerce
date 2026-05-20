# Estándares CI/CD — BR Innovation Projects

> **Alcance:** br-mt-ecommerce · hppt-iom  
> **Fecha:** 2026-05-20  
> **Versión:** 1.2  
> **Estado:** referencia operativa — alineada con Lineamientos CI/CD BR Innovation v1.0  
> **Fuente:** Lineamientos CI/CD — BR Innovation v1.0 (2026-05-20)  
> **Plan GitHub:** Free (repos privados)

---

## 0. Plan gratuito de GitHub — restricciones y alternativas

Los proyectos usan el **plan GitHub Free con repos privados**. Varias features del estándar ideal requieren plan Team ($4/user) o superior. Esta sección documenta qué está disponible, qué no, y la alternativa funcional que se usa en su lugar.

### Qué NO está disponible en repos privados con plan Free

| Feature | Requiere | Alternativa implementable en Free |
|---------|---------|-----------------------------------|
| **GitHub Environments con protection rules** (required reviewers, wait timers) | Team+ | `workflow_dispatch` con input de confirmación — ver §6 |
| **Branch protection rules** (require PR, status checks, required reviews) | Team+ para repos privados | Disciplina de equipo + `pr-checks.yml` como gate de CI |
| **CodeQL / code scanning nativo** | GitHub Advanced Security | Semgrep free tier (GitHub Action de terceros) |
| **Secret scanning nativo** | Solo public repos en Free | Gitleaks + Trufflehog como Actions — ✅ ya implementado |

### Qué SÍ está disponible en Free (repos privados)

| Feature | Límite / Nota |
|---------|--------------|
| **GitHub Actions** | 2,000 min/mes para repos privados — gestionar presupuesto (ver §0.1) |
| **GitHub Environments** | ✅ Sin protection rules — útil para scoping de secrets/variables por entorno |
| **GHCR (GitHub Container Registry)** | 500 MB storage · 1 GB/mes transfer — suficiente para 2-3 imágenes activas |
| **Dependabot security + version updates** | ✅ Disponible en todos los planes |
| **Gitleaks / Trufflehog como Actions** | ✅ Actions de terceros funcionan normalmente |
| **Trivy image scanning** | ✅ Action de terceros, sin límite de plan |
| **workflow_dispatch** (triggers manuales) | ✅ Disponible en Free |
| **Concurrency, timeouts, path filters** | ✅ Disponibles en Free |

### 0.1 Presupuesto de Actions (2,000 min/mes privados)

Con los workflows actuales, el consumo estimado por push a main que toca backend + frontend:

| Workflow | Jobs | Min estimados |
|----------|------|--------------|
| `ci-frontend` | lint + typecheck + test + build | ~20 min |
| `ci-backend` | lint + typecheck + test + security + build | ~25 min |
| `release-and-deploy` | build-backend + build-frontend + deploy | ~35 min |
| `secrets-scan` | gitleaks + trufflehog | ~10 min |
| **Total por release** | | **~90 min** |

Con ~2 releases por semana: ~720 min/mes → **36% del presupuesto libre**. Margen razonable. Si se supera el límite, las opciones son:
- Usar runners self-hosted (gratuitos, sin límite de minutos)
- Reducir la frecuencia de releases
- Consolidar workflows con `_reusable-ci.yml`

---

## 1. Principios no negociables

Todo workflow que viole uno de estos principios es técnicamente incorrecto, independientemente de que "funcione".

| # | Principio | Por qué es obligatorio |
|---|-----------|----------------------|
| **P1** | **Build once, deploy the same artifact** | Si producción reconstruye desde fuente, el artefacto desplegado nunca fue el que se testeó |
| **P2** | **CI verde es prerequisito al deploy, enforced — no convención** | Un deploy que puede ocurrir con CI roja no tiene pipeline de calidad |
| **P3** | **Lockfile frozen en todos los entornos** | `--no-frozen-lockfile` permite instalar versiones distintas a las testeadas |
| **P4** | **Secrets nunca en texto plano en comandos shell** | Cualquier `echo $SECRET` aparece en los logs del servidor destino |
| **P5** | **Migraciones de DB antes del deploy, siempre** | Código nuevo con schema viejo produce errores 500 en producción |
| **P6** | **Timeout en todos los jobs** | Sin timeout, un job colgado bloquea el runner hasta 6 horas |
| **P7** | **Actions de terceros pineadas a SHA completo** | Un tag `@v3` puede ser reescrito — vector de supply chain attack real |

---

## 2. Estructura de workflows requerida

Todo proyecto debe tener como mínimo estos workflows antes de considerarse listo para producción:

```
.github/
  workflows/
    ci.yml                     # lint + tests + build — corre en PR y push a ramas principales
    deploy-staging.yml         # deploy automático a staging tras CI verde en dev/develop
    deploy-production.yml      # deploy a producción, gateado por CI + aprobación manual
    rollback.yml               # rollback por workflow_dispatch — staging y producción
    secrets-scan.yml           # escaneo de secretos en PRs + cron semanal
    dependabot-auto-merge.yml  # auto-merge de patch/minor de Dependabot
  dependabot.yml               # configuración de Dependabot (ecosistemas npm/pip/actions)
```

### Opcional pero recomendado

```
  workflows/
    lighthouse.yml             # presupuesto de performance para proyectos con frontend
    _reusable-ci.yml           # workflow reutilizable (workflow_call) — ver §11
    semgrep.yml                # SAST de código con Semgrep (free tier, alternativa a CodeQL)
    openapi-sync.yml           # drift detection entre spec versionado y app FastAPI
```

> **Nota Free:** `codeql.yml` (GitHub native code scanning) **no está disponible para repos privados en Free**. Alternativa: [Semgrep](https://semgrep.dev) tiene un tier gratuito que funciona como GitHub Action sin restricción de plan.

---

## 3. Estado actual por proyecto

### 3.1 Cumplimiento de principios

| Principio | br-mt-ecommerce | hppt-iom |
|-----------|:--------------:|:--------:|
| P1 — Build once | ✅ GHCR inmutable | ❌ `--build` en servidor |
| P2 — CI gate enforced | ⚠️ Solo tags v*, no enforced | ❌ Push a main deploya directo |
| P3 — Frozen lockfile en prod | ❌ `--no-frozen-lockfile` | ✅ `npm ci` |
| P4 — Secrets sin exposición | ❌ GHCR token en SSH cmd | ❌ ENCRYPTION_KEY hardcodeada en YAML |
| P5 — Migraciones ordenadas | ❌ No corre alembic en deploy | ❌ Manual (checklist) |
| P6 — Timeouts en todos los jobs | ✅ | ❌ Solo deploy-production |
| P7 — SHA pin de actions | ❌ Tags mutables | ❌ Tags mutables |

### 3.2 Cumplimiento de workflows requeridos

| Workflow | br-mt-ecommerce | hppt-iom |
|----------|:--------------:|:--------:|
| `ci.yml` | ✅ (`ci-backend.yml` + `ci-frontend.yml`) | ✅ |
| `deploy-staging.yml` | ✅ (`release-and-deploy.yml`) | ✅ |
| `deploy-production.yml` | ⚠️ Mismo workflow, no gateado por CI | ❌ No gateado |
| `rollback.yml` | ✅ (`deploy-only.yml`) | ❌ Solo staging, no prod |
| `secrets-scan.yml` | ✅ Gitleaks + Trufflehog | ✅ Gitleaks |
| `dependabot-auto-merge.yml` | ✅ | ❌ |
| `dependabot.yml` | ✅ | ❌ |

### 3.3 Fortalezas únicas de cada proyecto

**br-mt-ecommerce tiene y hppt-iom necesita:**
- Cosign signing de imágenes Docker
- Trivy vulnerability scan antes del push a GHCR
- CodeQL SAST
- Dependabot con auto-merge de patch/minor
- Doble secrets scan (gitleaks + trufflehog)
- Rollback de producción via `workflow_dispatch`
- Alembic drift check en CI

**hppt-iom tiene y br-mt-ecommerce necesita:**
- SSH con `StrictHostKeyChecking=yes` + `known_hosts` verificado en producción
- Estructura `ci.yml` unificada (br-mt tiene ci-backend + ci-frontend separados, duplicando pasos)

---

## 4. Estructura del pipeline CI

### 4.1 Variables centralizadas (env: a nivel de workflow)

```yaml
env:
  NODE_VERSION: "20"
  PNPM_VERSION: "9.12.0"    # debe coincidir exactamente con packageManager en package.json
  PYTHON_VERSION: "3.11"
  UV_VERSION: "0.6.0"
  FRONTEND_DIR: mt-pricing-frontend
  BACKEND_DIR: mt-pricing-backend
```

### 4.2 Orden de jobs (siempre este orden)

```
lint ──┐
       ├──► test ──► build   (build solo en push a main/dev, no en PR)
typecheck ─┘
```

`lint` y `typecheck` corren en paralelo. `test` depende de ambos. `build` solo corre tras tests exitosos y únicamente en push a ramas principales.

### 4.3 Reglas de instalación de dependencias

```yaml
# Frontend — siempre frozen
- run: pnpm install --frozen-lockfile
# nunca: --no-frozen-lockfile

# Backend Python — siempre frozen
- run: uv sync --frozen

# Test runner frontend — nunca watch mode
- run: pnpm vitest run         # o: pnpm run test -- --run
# nunca: pnpm test (sin --run) → Vitest arranca en watch mode y cuelga el job 6h
```

### 4.4 Timeout obligatorio en todos los jobs

```yaml
jobs:
  lint:
    timeout-minutes: 10
  typecheck:
    timeout-minutes: 10
  test:
    timeout-minutes: 20
  build:
    timeout-minutes: 20
  deploy:
    timeout-minutes: 25
  rollback:
    timeout-minutes: 15
```

### 4.5 Coverage gate (mínimo requerido)

El umbral del 70% es el mínimo de entrada. Un proyecto nunca debe bajar del umbral establecido.

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 60,
      },
    },
  },
})
```

```ini
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=xml --cov-report=term-missing --cov-fail-under=70"
```

```yaml
# En el job de test del CI
- name: Test con coverage
  run: uv run pytest        # --cov-fail-under=70 está en pyproject.toml

# Frontend
- name: Test con coverage
  run: pnpm vitest run --coverage  # thresholds en vitest.config.ts
```

---

## 5. Pipeline de deploy

### 5.1 Diagrama de flujo obligatorio

```
push a develop/dev
       │
       ▼
  CI (lint + test + build)
       │ éxito
       ▼
  Build imagen → push a GHCR (tag: sha-<short>)
       │
       ▼
  Migraciones DB (alembic upgrade head / prisma migrate deploy)
       │
       ▼
  docker compose pull + up  ← imagen de GHCR, NUNCA --build en servidor
       │
       ▼
  Healthcheck (/health/live — TLS verificado, sin -k)
       │
       ▼
  Notificación Slack ──────────── éxito o falla


push a main / aprobación manual
       │
       ▼
  workflow_run: CI completó con éxito  ← gate enforced
       │
       ▼
  Aprobación manual (GitHub Environment: production + required reviewers)
       │
       ▼
  Promover imagen GHCR staging → producción (misma imagen, no rebuild)
       │
       ▼
  Migraciones DB en producción
       │
       ▼
  docker compose pull + up
       │
       ▼
  Healthcheck
       │
       ▼
  Tag de release automático (vYYYYMMDD-<sha>)
       │
       ▼
  Notificación Slack
```

### 5.2 Gate de CI antes de deploy a producción

```yaml
# deploy-production.yml
on:
  workflow_run:
    workflows: ["ci"]
    types: [completed]
    branches: [main]

jobs:
  deploy:
    if: github.event.workflow_run.conclusion == 'success'
    environment: production   # activa aprobación manual + secrets de entorno
    timeout-minutes: 45
```

### 5.3 Imagen inmutable — build en CI, pull en servidor

```yaml
# En CI: build y push con tag de SHA
- name: Build + push
  uses: docker/build-push-action@14487ce63c7a62a4a324b0bfb37086795e31c6c1  # v6.18.0
  with:
    push: true
    tags: |
      ghcr.io/${{ github.repository }}/app:sha-${{ github.sha }}
      ghcr.io/${{ github.repository }}/app:latest

# En el servidor: pull de la imagen ya validada (nunca --build en servidor)
- name: Deploy
  run: |
    ssh "$USER@$HOST" \
      "cd ~/app && \
       IMAGE_TAG=sha-${{ github.sha }} docker compose pull && \
       IMAGE_TAG=sha-${{ github.sha }} docker compose up -d --remove-orphans && \
       docker image prune -af"
```

### 5.4 Migraciones — siempre antes del `up`

```yaml
- name: Run DB migrations
  run: |
    ssh "${{ vars.SSH_USER }}@${{ secrets.SSH_HOST }}" \
      "cd ~/app && \
       docker compose run --rm backend alembic upgrade head"
       # o: prisma migrate deploy / flyway migrate
```

### 5.5 Healthcheck obligatorio

```yaml
- name: Healthcheck
  run: |
    HOST="${{ vars.STAGING_DOMAIN }}"
    for i in $(seq 1 24); do
      if curl -sf "https://$HOST/health/live" >/dev/null 2>&1; then
        echo "✓ OK after $((i*5))s"; exit 0
      fi
      echo "  attempt $i/24..."; sleep 5
    done
    echo "✗ FAILED after 120s"; exit 1
# curl sin -k — si el certificado TLS falla, el healthcheck falla (correcto)
```

### 5.6 Diferencias staging vs producción

| Aspecto | Staging | Producción |
|---------|---------|------------|
| Trigger | Push a `develop` | `workflow_run` gateado por CI |
| `cancel-in-progress` | `true` | `false` (nunca cortar un deploy en curso) |
| GitHub Environment | `staging` (sin reviewers) | `production` (required reviewers) |
| SSH known_hosts | `ssh-keyscan` aceptable | Secret `PROD_SSH_KNOWN_HOST` requerido |
| Notificaciones | Recomendado | **Obligatorio** |

---

## 6. GitHub Environments — configuración disponible en Free

> **Restricción Free:** Los Environments existen y funcionan para scoping de secrets/variables, pero las **protection rules** (required reviewers, wait timers) **no están disponibles en repos privados con plan Free**. La alternativa es un gate de confirmación via `workflow_dispatch`.

### Configuración de environments (Settings → Environments)

```
staging:
  ├── Protection rules: ninguna (Free no las soporta en repos privados)
  ├── Secrets: STAGING_SSH_KEY, STAGING_SSH_HOST, STAGING_SSH_USER, ENV_STAGING
  └── Variables: STAGING_DOMAIN

production:
  ├── Protection rules: ninguna en Free ← ver alternativa abajo
  ├── Secrets: PROD_SSH_KEY, PROD_SSH_HOST, PROD_SSH_USER, PROD_SSH_KNOWN_HOST, ENV_PRODUCTION
  └── Variables: PROD_DOMAIN
```

Los environments se usan igualmente para scoping de secrets — los secrets de `production` solo son accesibles desde el job que declara `environment: production`.

### Alternativa al approval manual — workflow_dispatch con confirmación

Sin protection rules, el gate de producción se implementa via `workflow_dispatch` con un input de confirmación obligatorio:

```yaml
# deploy-production.yml
name: deploy-production

on:
  workflow_dispatch:
    inputs:
      confirm:
        description: "Escribe 'deploy' para confirmar el deploy a producción"
        required: true
      tag:
        description: "Tag de imagen a desplegar (e.g. v1.2.3 o sha-abc1234)"
        required: true

jobs:
  guard:
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - name: Verify confirmation
        run: |
          if [ "${{ github.event.inputs.confirm }}" != "deploy" ]; then
            echo "✗ Confirmación inválida. Escribe exactamente 'deploy'."
            exit 1
          fi
          echo "✓ Confirmación aceptada"

  deploy:
    needs: guard
    environment: production    # scoping de secrets, sin protection rules en Free
    runs-on: ubuntu-latest
    timeout-minutes: 25
    ...
```

Este patrón garantiza que el deploy a producción es **siempre intencional** (no puede ocurrir por un push accidental) aunque no requiere aprobación de otro usuario.

### Si el plan sube a Team — agregar sin cambios en el workflow

```
production environment → Deployment protection rules:
  ├── Required reviewers: [tech lead + 1 más]
  └── Wait timer: 0 min
```

El workflow no cambia — GitHub bloquea el job automáticamente hasta que un reviewer apruebe.

---

## 7. Rollback — estándar para ambos proyectos

Todo proyecto en producción debe tener rollback automatizado.

```yaml
# .github/workflows/rollback.yml
name: rollback

on:
  workflow_dispatch:
    inputs:
      environment:
        description: "staging / production"
        required: true
        type: choice
        options: [staging, production]
      tag:
        description: "Tag de imagen a restaurar (e.g. sha-abc1234 o v1.2.3)"
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2

      - name: Setup SSH
        uses: webfactory/ssh-agent@a3daa3d7af84f4a6bca2f7b396fb40c8f5e9bd5f  # v0.9.1
        with:
          ssh-private-key: ${{ secrets[format('{0}_SSH_KEY', upper(inputs.environment))] }}

      - name: Verify host key
        run: |
          mkdir -p ~/.ssh
          ssh-keyscan -H \
            "${{ secrets[format('{0}_SSH_HOST', upper(inputs.environment))] }}" \
            >> ~/.ssh/known_hosts

      - name: Pull tag + restart
        env:
          HOST: ${{ secrets[format('{0}_SSH_HOST', upper(inputs.environment))] }}
          USER: ${{ secrets[format('{0}_SSH_USER', upper(inputs.environment))] }}
          TAG: ${{ inputs.tag }}
        run: |
          ssh "$USER@$HOST" \
            "cd ~/app && \
             IMAGE_TAG=${TAG} docker compose pull && \
             IMAGE_TAG=${TAG} docker compose up -d --remove-orphans"

      - name: Healthcheck
        run: |
          DOMAIN="${{ vars[format('{0}_DOMAIN', upper(inputs.environment))] }}"
          for i in $(seq 1 18); do
            curl -sf "https://$DOMAIN/health/live" && echo "✓ OK" && exit 0
            sleep 5
          done
          exit 1
```

---

## 8. Gestión de secrets y variables

### 8.1 Clasificación obligatoria

| Tipo de dato | Dónde guardar | Ejemplo |
|---|---|---|
| Clave SSH privada | GitHub Secret | `STAGING_SSH_KEY` |
| Token de API externo | GitHub Secret | `ANTHROPIC_API_KEY` |
| Contenido del `.env` del servidor | GitHub Secret | `ENV_STAGING` |
| Token de registry (GHCR) | Configurado en el servidor, no en el workflow | ver §8.2 |
| URL pública no sensible | GitHub Variable (`vars.*`) | `NEXT_PUBLIC_BACKEND_URL` |
| Dominio del servidor | GitHub Variable | `STAGING_DOMAIN` |
| Versiones de herramientas | `env:` en el workflow | `PNPM_VERSION: "9.12.0"` |

### 8.2 Token de GHCR — patrón correcto

```yaml
# ❌ Incorrecto — el token aparece en los logs del servidor
run: |
  ssh user@host "echo '${{ secrets.GITHUB_TOKEN }}' | docker login ghcr.io -u user --password-stdin"

# ✅ Correcto — configurar credenciales en el servidor una sola vez (setup inicial)
# En el servidor: echo $TOKEN | docker login ghcr.io -u $USER --password-stdin
# Docker guarda las credenciales en ~/.docker/config.json
# El workflow solo hace pull, sin pasar credenciales:
run: |
  ssh "$USER@$HOST" "cd ~/app && IMAGE_TAG=${TAG} docker compose pull"
```

### 8.3 Secrets en tests — generar efímeramente

```yaml
# ❌ Incorrecto — clave hardcodeada en el YAML del repositorio
env:
  ENCRYPTION_KEY: qTkKP-X97AZDiI6BYxuSiV0CkHiRdhJ5XkqwIJxESiA=

# ✅ Correcto — generada en el step, nunca persistida
- name: Generate test encryption key
  run: |
    echo "ENCRYPTION_KEY=$(python -c \
      'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
      >> "$GITHUB_ENV"
```

---

## 9. Seguridad del pipeline

### 9.1 SHA pinning de actions

```yaml
# ❌ Incorrecto — tags mutables
- uses: actions/checkout@v4
- uses: trufflesecurity/trufflehog@main   # máximo riesgo: rama directa

# ✅ Correcto — SHA inmutable del commit del tag
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683      # v4.2.2
- uses: trufflesecurity/trufflehog@v3.88.27
```

**SHAs de referencia (verificar antes de usar):**

| Action | Versión | SHA |
|--------|---------|-----|
| `actions/checkout` | v4.2.2 | `11bd71901bbe5b1630ceea73d27597364c9af683` |
| `actions/setup-node` | v4.4.0 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `pnpm/action-setup` | v4.1.0 | `a3252b7d33c8a4e462e2012f8ad67a08da2e7fd1` |
| `docker/build-push-action` | v6.18.0 | `14487ce63c7a62a4a324b0bfb37086795e31c6c1` |
| `docker/login-action` | v3.4.0 | `74a5d142397b4f367a81961eba4e8cd7edddf772` |
| `astral-sh/setup-uv` | v5.4.1 | `f0ec1fc3b38f5e7cd731bb6ce540c5af426746bb` |
| `webfactory/ssh-agent` | v0.9.1 | `a3daa3d7af84f4a6bca2f7b396fb40c8f5e9bd5f` |

Obtener SHA de cualquier action:
```bash
gh api /repos/{owner}/{repo}/git/ref/tags/{tag} --jq '.object.sha'
```

### 9.2 Permisos mínimos

```yaml
# A nivel de workflow — mínimo global
permissions:
  contents: read

jobs:
  deploy:
    permissions:
      contents: write    # solo los jobs que lo necesitan
      packages: write
```

### 9.3 Secrets scanning

Mínimo: Gitleaks. Recomendado: Gitleaks + Trufflehog (engines distintos, mayor cobertura).

```yaml
# .github/workflows/secrets-scan.yml
on:
  pull_request:
    branches: [main, develop, dev]
  push:
    branches: [main, develop, dev]
  schedule:
    - cron: '0 5 * * 1'   # lunes 05:00 UTC

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  trufflehog:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    continue-on-error: true   # advisory — no bloquea hasta calibrar falsos positivos
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683
        with:
          fetch-depth: 0
      - uses: trufflesecurity/trufflehog@v3.88.27
        with:
          extra_args: --only-verified
```

### 9.4 SSH endurecido

```yaml
# Producción — known_hosts desde secret (no ssh-keyscan en producción)
- name: Verify host key
  run: |
    mkdir -p ~/.ssh
    echo "${{ secrets.PROD_SSH_KNOWN_HOST }}" >> ~/.ssh/known_hosts
    # PROD_SSH_KNOWN_HOST se obtiene una sola vez con: ssh-keyscan -H <host>

# Staging — ssh-keyscan aceptable
- name: Verify host key
  run: |
    mkdir -p ~/.ssh
    ssh-keyscan -H "${{ secrets.STAGING_SSH_HOST }}" >> ~/.ssh/known_hosts
```

Nunca usar `-o StrictHostKeyChecking=no`. La flag correcta es `StrictHostKeyChecking=yes`.

### 9.5 Vulnerability scanning de imágenes

```yaml
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: ghcr.io/${{ github.repository }}/app:sha-${{ github.sha }}
    format: sarif
    output: trivy-results.sarif
    severity: CRITICAL,HIGH
    exit-code: '1'         # falla el build si hay vulnerabilidades críticas/altas
    ignore-unfixed: true   # no falla por vulns sin fix disponible

- name: Upload results
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: trivy-results.sarif
```

---

## 10. Notificaciones

Todo deploy a producción **debe** notificar el resultado (éxito o falla). Staging es recomendado.

```yaml
# Al final de cualquier deploy job
- name: Notify success
  if: success()
  uses: slackapi/slack-github-action@v2.1.0
  with:
    webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
    webhook-type: incoming-webhook
    payload: |
      {
        "text": "✅ Deploy *${{ github.repository }}* → `${{ github.ref_name }}` completado.",
        "attachments": [{
          "color": "good",
          "fields": [
            {"title": "Commit", "value": "${{ github.sha }}", "short": true},
            {"title": "Actor", "value": "${{ github.actor }}", "short": true}
          ]
        }]
      }

- name: Notify failure
  if: failure()
  uses: slackapi/slack-github-action@v2.1.0
  with:
    webhook: ${{ secrets.SLACK_WEBHOOK_URL }}
    webhook-type: incoming-webhook
    payload: |
      {
        "text": "❌ Deploy *${{ github.repository }}* falló en `${{ github.ref_name }}`.",
        "attachments": [{
          "color": "danger",
          "fields": [{
            "title": "Run",
            "value": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          }]
        }]
      }
```

**Eventos que deben notificar:**
- Fallo de CI en rama principal
- Deploy exitoso a producción
- Fallo de deploy a producción
- Rollback ejecutado (cualquier entorno)

**Secret requerido:** `SLACK_WEBHOOK_URL` — Incoming Webhook de Slack configurado por canal.

---

## 11. Reusable workflows — evitar duplicación

Cuando el mismo conjunto de pasos de CI es consumido por múltiples workflows (ej. `ci.yml` y `deploy-staging.yml`), extraerlo a un reusable workflow. Convención de nombre: prefijo `_`.

```yaml
# .github/workflows/_reusable-ci.yml
name: _reusable-ci

on:
  workflow_call:
    inputs:
      run-build:
        type: boolean
        default: false
      working-directory:
        type: string
        default: '.'
    secrets:
      ENCRYPTION_KEY:
        required: false

jobs:
  frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    defaults:
      run:
        working-directory: mt-pricing-frontend
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
      - uses: pnpm/action-setup@v6
        with:
          version: 9.12.0
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020  # v4.4.0
        with:
          node-version: "20"
          cache: pnpm
          cache-dependency-path: mt-pricing-frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm run lint
      - run: pnpm vitest run --coverage
      - if: inputs.run-build
        run: pnpm run build

  backend:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    defaults:
      run:
        working-directory: mt-pricing-backend
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
      - uses: astral-sh/setup-uv@f0ec1fc3b38f5e7cd731bb6ce540c5af426746bb  # v5.4.1
        with:
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pytest    # thresholds en pyproject.toml
```

```yaml
# ci.yml — consume el reusable
name: ci
on:
  push:
    branches: [main, develop, dev]
  pull_request:

jobs:
  ci:
    uses: ./.github/workflows/_reusable-ci.yml
    secrets: inherit
```

```yaml
# deploy-staging.yml — consume el mismo reusable antes del deploy
jobs:
  verify:
    uses: ./.github/workflows/_reusable-ci.yml
    secrets: inherit

  deploy:
    needs: verify
    ...
```

---

## 12. Branch strategy

### 12.1 Estructura de ramas

```
main          → producción (merge solo via PR — enforcement manual en Free)
develop / dev → staging (merge solo via PR — enforcement manual en Free)
feature/*     → desarrollo individual, CI only
hotfix/*      → fix urgente: PR a main + cherry-pick / back-merge a develop
```

### 12.2 Branch protection rules

> **Restricción Free:** Las branch protection rules para **repos privados** requieren plan Team+. En plan Free solo están disponibles para repos públicos.  
> **Alternativa:** El `pr-checks.yml` con commitlint + semantic PR title actúa como gate de calidad en PRs, y el gate de CI en `deploy-production.yml` previene deploys con código roto.

**Configurar manualmente en el equipo (disciplina de proceso):**
- Nunca hacer push directo a `main` ni a `develop`
- Siempre crear PR — el `pr-checks.yml` valida conventional commits y título del PR
- No mergear un PR con CI roja

**Si el plan sube a Team — configurar en Settings → Branches:**

```
Para main y develop:
  ✅ Require a pull request before merging
      ✅ Require approvals: 1
      ✅ Dismiss stale pull request approvals when new commits are pushed
  ✅ Require status checks to pass (lint, typecheck, test, build)
  ✅ Require branches to be up to date before merging
  ✅ Require conversation resolution before merging
  ✅ Require linear history
  ✅ Do not allow bypassing the above settings
```

### 12.3 Política de merge

| Tipo de PR | Merge strategy | Por qué |
|-----------|---------------|---------|
| `feature/*` → `develop` | **Squash merge** | Un commit limpio por feature |
| `hotfix/*` → `main` | **Merge commit** | Preservar la firma del hotfix para audit |
| `develop` → `main` | **Merge commit** | Preservar el historial de staging |

El título del PR squash se convierte en el mensaje de commit — debe seguir conventional commits format.

---

## 13. PR hygiene

### 13.1 Conventional commits

Todos los commits (y títulos de PR) deben seguir el formato:

```
<tipo>(<scope opcional>): <descripción en imperativo>

feat(auth): add OAuth2 login with Google
fix(api): handle null response from payment gateway
chore(deps): bump pnpm to 9.12.0
docs(readme): add local dev setup instructions
ci(workflows): pin all actions to SHA
```

**Tipos válidos:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `revert`

### 13.2 Configuración de commitlint

```yaml
# .commitlintrc.yml
extends:
  - '@commitlint/config-conventional'
rules:
  header-max-length: [2, always, 100]
  body-max-line-length: [2, always, 200]
```

### 13.3 Workflow de PR checks

```yaml
# .github/workflows/pr-checks.yml
name: pr-checks
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  commitlint:
    name: Conventional commits
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
        with:
          fetch-depth: 0
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020  # v4.4.0
        with:
          node-version: "20"
      - run: npm install --no-save @commitlint/cli@19 @commitlint/config-conventional@19
      - run: |
          npx commitlint \
            --from "${{ github.event.pull_request.base.sha }}" \
            --to   "${{ github.event.pull_request.head.sha }}" \
            --verbose

  pr-title:
    name: Semantic PR title
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            docs
            style
            refactor
            perf
            test
            build
            ci
            chore
            revert
```

---

## 14. Gestión de dependencias

### 14.1 `dependabot.yml` completo

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: npm
    directory: /mt-pricing-frontend
    schedule:
      interval: weekly
      day: monday
    target-branch: develop
    groups:
      patch-updates:
        update-types: [patch]
      minor-updates:
        update-types: [minor]
    ignore:
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]  # major = revisión manual

  - package-ecosystem: pip
    directory: /mt-pricing-backend
    schedule:
      interval: weekly
      day: monday
    target-branch: develop

  - package-ecosystem: docker
    directory: /
    schedule:
      interval: weekly
      day: monday
    target-branch: develop

  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
      day: monday     # mantiene SHAs de actions actualizados automáticamente
```

### 14.2 Auto-merge de patch y minor

```yaml
# .github/workflows/dependabot-auto-merge.yml
name: dependabot-auto-merge
on: pull_request

permissions:
  contents: read

jobs:
  auto-merge:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    timeout-minutes: 5
    permissions:
      contents: write      # solo este job necesita escribir
      pull-requests: write
    steps:
      - name: Fetch metadata
        id: meta
        uses: dependabot/fetch-metadata@v2.4.0
      - name: Auto-merge patch/minor
        if: |
          steps.meta.outputs.update-type == 'version-update:semver-patch' ||
          steps.meta.outputs.update-type == 'version-update:semver-minor'
        run: gh pr merge --auto --squash "$PR_URL"
        env:
          PR_URL: ${{ github.event.pull_request.html_url }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 15. Correcciones concretas por proyecto

### 15.1 br-mt-ecommerce — cambios pendientes

#### Fix 1: IP hardcodeada → variable de repositorio (`release-and-deploy.yml:187`)
```yaml
# ❌ Actual
NEXT_PUBLIC_BACKEND_URL: https://100-53-214-97.sslip.io

# ✅ Correcto
NEXT_PUBLIC_BACKEND_URL: ${{ vars.NEXT_PUBLIC_BACKEND_URL }}
```
*Configurar en GitHub → Settings → Variables → `NEXT_PUBLIC_BACKEND_URL`*

#### Fix 2: pnpm frozen + versión correcta (`release-and-deploy.yml:167,178`)
```yaml
# ❌ Actual
uses: pnpm/action-setup@v6
  version: 9.0.0
run: pnpm install --no-frozen-lockfile

# ✅ Correcto
uses: pnpm/action-setup@v6
  version: 9.12.0
run: pnpm install --frozen-lockfile --filter mt-pricing-frontend...
```

#### Fix 3: Migraciones Alembic en deploy (`release-and-deploy.yml` — agregar step)
```yaml
# Agregar ANTES del step "Pull images + deploy"
- name: Run DB migrations
  run: |
    ssh "${{ secrets.STAGING_SSH_USER }}@${{ secrets.STAGING_SSH_HOST }}" \
      "cd ~/app && \
       docker compose -f docker-compose.staging.yml run --rm backend \
         alembic upgrade head"
```

#### Fix 4: Healthcheck sin `-k` (`release-and-deploy.yml:286`)
```yaml
# ❌ Actual
if curl -sfk "https://$HOST/health/live"
# ✅ Correcto
if curl -sf "https://$HOST/health/live"
```

#### Fix 5: `openapi-sync.yml` — reemplazar npm por pnpm
```yaml
# ❌ Actual — npm ci con package-lock.json que no existe en proyecto pnpm
- uses: actions/setup-node@v4
  with:
    cache: "npm"
    cache-dependency-path: mt-pricing-frontend/package-lock.json
- run: npm ci --no-audit --no-fund

# ✅ Correcto
- uses: pnpm/action-setup@v6
  with:
    version: 9.12.0
- uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: pnpm
    cache-dependency-path: mt-pricing-frontend/pnpm-lock.yaml
- run: pnpm install --frozen-lockfile
```

#### Fix 6: `trufflehog@main` → tag de release (`secrets-scan.yml:81`)
```yaml
# ❌ Actual — rama directa, máximo riesgo
uses: trufflesecurity/trufflehog@main

# ✅ Correcto
uses: trufflesecurity/trufflehog@v3.88.27
```

#### Fix 7: `dependabot-auto-merge.yml` — mover permisos al job
```yaml
# ❌ Actual — permisos a nivel de workflow
permissions:
  contents: write
  pull-requests: write

# ✅ Correcto — mínimo en workflow, permisos solo en el job
permissions:
  contents: read

jobs:
  auto-merge:
    permissions:
      contents: write
      pull-requests: write
```

### 15.2 hppt-iom — cambios pendientes

#### Fix 1 (P1): Artefacto inmutable — build en CI, pull en servidor
```yaml
# ❌ Actual en deploy-production.yml
ssh user@prod "git pull && docker compose up --build"

# ✅ Correcto — mismo patrón GHCR que staging
ssh user@prod \
  "cd ~/app && IMAGE_TAG=${TAG} docker compose pull && \
   docker compose up -d --remove-orphans"
```

#### Fix 2 (P1): Gate CI antes de deploy-production
```yaml
# ❌ Actual — push a main deploya directo
on:
  push:
    branches: [main]

# ✅ Correcto
on:
  workflow_run:
    workflows: ["ci"]
    types: [completed]
    branches: [main]

jobs:
  deploy:
    if: github.event.workflow_run.conclusion == 'success'
    environment: production
```

#### Fix 3 (P1): Fix Vitest watch mode — `staging-deploy.yml:44`
```yaml
# ❌ Actual — cuelga hasta timeout de 6h
run: npm run test

# ✅ Correcto
run: npm run test -- --run
```

#### Fix 4: Timeouts en todos los jobs
```yaml
jobs:
  frontend:
    timeout-minutes: 20
  backend:
    timeout-minutes: 20
  deploy:
    timeout-minutes: 25
```

#### Fix 5: ENCRYPTION_KEY efímera
```yaml
# ❌ Actual — clave hardcodeada en YAML
ENCRYPTION_KEY: qTkKP-X97AZDiI6BYxuSiV0CkHiRdhJ5XkqwIJxESiA=

# ✅ Correcto — generada efímeramente
- name: Generate test encryption key
  run: |
    echo "ENCRYPTION_KEY=$(python -c \
      'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')" \
      >> "$GITHUB_ENV"
```

#### Fix 6: Crear `rollback.yml` para producción
Ver plantilla completa en §7.

---

## 16. Plan de implementación priorizado

### Semana 1 — Críticos (< 2h total)

| # | Cambio | Proyecto | Archivo | Tiempo |
|---|--------|----------|---------|--------|
| 1 | IP hardcodeada → `vars.NEXT_PUBLIC_BACKEND_URL` | br-mt | `release-and-deploy.yml:187` | 5 min |
| 2 | `--no-frozen-lockfile` → `--frozen-lockfile` + pnpm 9.12.0 | br-mt | `release-and-deploy.yml:167,178` | 10 min |
| 3 | `npm ci` → `pnpm install --frozen-lockfile` | br-mt | `openapi-sync.yml:93` | 15 min |
| 4 | `trufflehog@main` → `trufflehog@v3.88.27` | br-mt | `secrets-scan.yml:81` | 5 min |
| 5 | Fix Vitest watch mode bug | hppt-iom | `staging-deploy.yml:44` | 5 min |
| 6 | Timeouts en todos los jobs | hppt-iom | `ci.yml`, `staging-deploy.yml` | 20 min |
| 7 | ENCRYPTION_KEY efímera | hppt-iom | `ci.yml`, `staging-deploy.yml` | 10 min |

### Semana 2 — Importantes (< 1 día total)

| # | Cambio | Proyecto | Tiempo |
|---|--------|----------|--------|
| 8 | Agregar step alembic en deploy | br-mt | 30 min |
| 9 | Healthcheck sin `-k` | br-mt | 5 min |
| 10 | `dependabot-auto-merge.yml`: permisos al job | br-mt | 10 min |
| 11 | Slack notifications en deploy producción | ambos | 30 min |
| 12 | Crear `rollback.yml` para producción | hppt-iom | 45 min |
| 13 | Gate CI antes de deploy-production | hppt-iom | 30 min |
| 14 | GitHub Environment `production` con reviewers | ambos | 15 min |
| 15 | Coverage gate en vitest.config.ts y pyproject.toml | ambos | 20 min |

### Semana 3 — Mejoras (< 2 días total)

| # | Cambio | Proyecto | Tiempo |
|---|--------|----------|--------|
| 16 | Build once + GHCR para producción | hppt-iom | 3-4h |
| 17 | SHA pinning de todas las actions | ambos | 2h |
| 18 | Branch protection rules en GitHub | ambos | 30 min |
| 19 | `_reusable-ci.yml` para eliminar duplicación | ambos | 3h |
| 20 | Job E2E nightly (Playwright) | ambos | 1 día |
| 21 | CodeQL + Dependabot para hppt-iom | hppt-iom | 1h |

---

## 17. Checklist de validación

Usar antes de considerar el pipeline de un proyecto como completo.

> **Leyenda:** ✅ disponible en Free · 💰 requiere plan Team+ (anotar como deuda técnica si no se implementa)

### Arquitectura (todo disponible en Free)
- [ ] Existe `ci.yml` con lint + test + build ✅
- [ ] Existe `deploy-staging.yml` con CI gate ✅
- [ ] Existe `deploy-production.yml` con `workflow_dispatch` + input de confirmación ✅
- [ ] Existe `rollback.yml` para staging **y** producción ✅
- [ ] Existe `secrets-scan.yml` con cron semanal ✅
- [ ] Existe `.github/dependabot.yml` con ecosistemas npm/pip/github-actions ✅
- [ ] Existe `dependabot-auto-merge.yml` ✅

### Seguridad (todo disponible en Free salvo lo marcado)
- [ ] Ninguna action usa `@main`, `@master` o tag mutable — todas pineadas a SHA ✅
- [ ] Ningún workflow expone secrets en comandos shell (`echo $SECRET | cmd`) ✅
- [ ] Permisos declarados a nivel de job (no de workflow como default) ✅
- [ ] `deploy-production.yml` usa `workflow_dispatch` con input de confirmación ✅ (alternativa a required reviewers)
- [ ] GitHub Environment `production` con required reviewers 💰 *(Team+ — deuda técnica si no se tiene)*
- [ ] `.env` de producción nunca en el repositorio — solo como GitHub Secret ✅
- [ ] SSH usa `StrictHostKeyChecking=yes` en producción ✅
- [ ] Imágenes escaneadas con Trivy antes del push a GHCR ✅
- [ ] SAST de código con Semgrep (alternativa a CodeQL para repos privados en Free) ✅

### Confiabilidad del pipeline (todo disponible en Free)
- [ ] Todos los jobs tienen `timeout-minutes` ✅
- [ ] Tests frontend usan `--run` (no watch mode) ✅
- [ ] Frontend usa `--frozen-lockfile` ✅
- [ ] Backend usa `uv sync --frozen` o requirements pineados ✅
- [ ] Versión de pnpm en workflows == `packageManager` en `package.json` ✅
- [ ] Coverage gate configurado (mínimo 70% líneas/funciones) ✅

### Pipeline de calidad (todo disponible en Free)
- [ ] CI verde es prerequisito enforced antes de cualquier deploy a producción ✅
- [ ] Imagen en producción es la misma que pasó CI (no `--build` en servidor) ✅
- [ ] Migraciones DB corren antes del `docker compose up` ✅
- [ ] Healthcheck sin `-k` (TLS verificado) ✅
- [ ] Rollback automatizado disponible para producción ✅
- [ ] Branch protection rules en ramas principales 💰 *(Team+ para repos privados — enforcement manual hasta entonces)*

### Operaciones (todo disponible en Free)
- [ ] Notificaciones a Slack configuradas (mínimo: fallos de CI + deploys de producción) ✅
- [ ] Release tags creados automáticamente en cada deploy de producción ✅
- [ ] Logs accesibles via `docker compose logs` en el servidor ✅
- [ ] Existe runbook de rollback documentado y accesible para el equipo ✅

---

## 18. Alineación con estándares de la industria

| Estándar | Control | Estado br-mt | Estado hppt-iom |
|----------|---------|:-----------:|:--------------:|
| **DORA High Performer** | Deploy frecuente y confiable | ⚠️ Parcial | ⚠️ Parcial |
| **DORA Elite Performer** | MTTR < 1h, change failure rate < 5% | ❌ Sin rollback prod en iOM | ❌ |
| **SLSA Level 1** | Build scripted, no manual | ✅ | ✅ |
| **SLSA Level 2** | Build en CI + SHA pin de actions | ⚠️ Falta SHA pin | ⚠️ Falta SHA pin |
| **SLSA Level 3** | Cosign signing de imágenes | ✅ (br-mt) | ❌ |
| **OWASP CI/CD #1** | Insufficient Flow Control (CI gate) | ⚠️ Solo tags | ❌ |
| **OWASP CI/CD #2** | Inadequate Identity & Auth | ✅ GHCR + cosign | ⚠️ Sin image signing |
| **OWASP CI/CD #3** | Dependency Chain Abuse | ⚠️ Falta SHA pin | ⚠️ Falta SHA pin |
| **OWASP CI/CD #6** | Insufficient Credential Hygiene | ❌ GHCR token en SSH | ❌ Clave hardcodeada |
| **12-Factor App #5** | Build/release/run separados | ✅ | ❌ (--build en prod) |
| **12-Factor App #3** | Config en environment | ⚠️ IP hardcodeada | ✅ |
| **CDF Best Practices** | Pipeline as code, rollback definido | ✅ / ⚠️ | ⚠️ |

### Restricciones de plan y su impacto en estándares

| Estándar afectado | Feature bloqueada por plan Free | Alternativa implementada |
|---|---|---|
| OWASP CI/CD #1 (Flow Control) | Branch protection rules (private repos) | `pr-checks.yml` + disciplina de equipo |
| DORA Elite (change failure rate) | Required reviewers en Environments | `workflow_dispatch` con input confirmación |
| SLSA L2 (provenance) | CodeQL (GitHub native) | Semgrep + Trivy + Gitleaks |
| CDF (aprobación antes de prod) | Environment protection rules | Manual trigger con confirmación |

Un proyecto que cumple todos los ítems del checklist §17 opera como **DORA High Performer**. La adición de Cosign signing y E2E nightly lo acerca a **Elite Performer**.

---

## Historial de versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.2 | 2026-05-20 | Ajuste para plan GitHub Free: §0 con tabla de restricciones y alternativas, presupuesto de Actions, §6 reemplaza required reviewers por workflow_dispatch con confirmación, §12 documenta branch protection como deuda técnica, checklist con leyenda Free/💰, tabla de impacto en estándares |
| 1.1 | 2026-05-20 | Alineación completa con Lineamientos CI/CD BR Innovation v1.0: workflows requeridos, coverage gate, Slack, reusable workflows, branch strategy, PR hygiene, dependabot.yml completo, tabla DORA/SLSA/OWASP, checklist extendido |
| 1.0 | 2026-05-20 | Versión inicial — consolidación de análisis br-mt-ecommerce y hppt-iom |
