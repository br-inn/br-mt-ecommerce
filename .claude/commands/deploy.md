Desplegar todos los cambios al servidor de staging en Hetzner vía GitHub Actions.

Argumentos opcionales: `$ARGUMENTS`
- Sin argumentos: auto-incrementa el último tag UAT (e.g. v0.5.1-uat → v0.5.2-uat)
- Si se provee un tag (e.g. `v0.6.0-uat`): usa ese tag exacto

## Pasos

### 1. Revisar estado del repositorio

Ejecuta en Bash:
```
git status --short
git log --oneline -3
git tag --sort=-version:refname | head -3
```

### 2. Stagear y commitear cambios de código fuente

Stagear **únicamente** archivos de código fuente (excluir `.claude/`, `.cursor/`, `*.png`, `*.pdf`, archivos temporales, `.env*`):

```bash
git add \
  mt-pricing-backend/app/ \
  mt-pricing-backend/alembic/versions/ \
  mt-pricing-backend/tests/ \
  mt-pricing-backend/scripts/ \
  mt-pricing-frontend/app/ \
  mt-pricing-frontend/components/ \
  mt-pricing-frontend/lib/ \
  mt-pricing-frontend/messages/ \
  mt-pricing-frontend/public/ \
  _bmad-output/implementation-artifacts/sprint-status.yaml \
  2>/dev/null || true
```

Si hay cambios staged (`git diff --cached --stat` muestra archivos), crear commit:
- Revisar `git diff --cached --stat` para entender qué cambió
- Mensaje de commit conciso en formato convencional: `feat/fix/perf(scope): descripción`
- Si NO hay nada staged nuevo (todo ya commiteado), saltar al paso 3

### 3. Pull rebase para integrar cambios remotos

```bash
git pull --rebase origin main
```

Si falla por cambios sin stagear (unstaged):
```bash
git stash
git pull --rebase origin main
git stash pop
```

### 4. Push a main

```bash
git push origin main
```

Si es rechazado (non-fast-forward), reintentar pull rebase + push.

### 5. Calcular próximo tag

- Leer el último tag: `git tag --sort=-version:refname | head -1`
- Si el argumento `$ARGUMENTS` está vacío: auto-incrementar el patch del último tag UAT
  - Ejemplo: `v0.5.1-uat` → `v0.5.2-uat`
  - Patrón: `vMAJOR.MINOR.PATCH-uat` → incrementar PATCH
- Si `$ARGUMENTS` tiene un tag: usarlo directamente

### 6. Crear y pushear tag

```bash
git tag <nuevo-tag>
git push origin <nuevo-tag>
```

### 7. Reportar resultado

Informar:
- Commit pusheado (hash + mensaje)
- Tag creado y pusheado
- URL de GitHub Actions para seguir el progreso:
  `https://github.com/br-inn/br-mt-ecommerce/actions`

El pipeline de GitHub Actions corre automáticamente:
1. `release-images` — build backend + frontend → push imágenes a GHCR
2. `deploy-staging` — SSH a Hetzner → `docker compose pull && up -d` + healthcheck

## Notas

- NUNCA commitear: `.env*`, `.claude/settings*`, `*.png`, `*.pdf`, archivos temporales en raíz
- Si `git pull --rebase` genera conflictos, reportarlos al usuario y no continuar
- El tag DEBE seguir el patrón `v*` para disparar `release-images`
