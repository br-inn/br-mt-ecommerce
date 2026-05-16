# US-SCR-03-01: i18n, RBAC y Navegación para Competitor Brands

**Status:** review
**Fecha:** 2026-05-16
**Branch:** main

## Cambios realizados

### Frontend — RBAC

- `mt-pricing-frontend/app/(app)/admin/competitor-brands/page.tsx`
  - Cambiado permiso de `products:read` a `admin:read` en `RbacGuard`
  - Reemplazado string hardcodeado en fallback por `{t("noPermission")}`

### Frontend — i18n

- `mt-pricing-frontend/app/(app)/admin/competitor-brands/_client.tsx`
  - Reemplazado `"Cargando marcas..."` (línea 339) por `{t("loading")}`

- `mt-pricing-frontend/messages/es.json` — añadidas keys:
  - `admin.competitorBrands.noPermission`
  - `admin.competitorBrands.loading`

- `mt-pricing-frontend/messages/en.json` — añadidas keys equivalentes en inglés

- `mt-pricing-frontend/messages/ar.json` — añadidas keys equivalentes en árabe

### Frontend — Navegación (sidebar)

- `mt-pricing-frontend/components/shell/sidebar.tsx`
  - `SECTION_SYS_ADMIN`: entrada "Marcas competidoras" cambia de `permissions: ["products:read"]` a `permissions: ["admin:read"]`
  - Resultado: solo roles `ti_integracion`, `gerente_comercial` y `admin` ven el link (rol `comercial` ya no lo ve)

## Acceptance Criteria verificados

1. Todos los textos de `/admin/competitor-brands` usan `t('admin.competitorBrands.*')` — cero strings hardcodeados
2. Keys añadidas en `messages/es.json`, `messages/en.json`, `messages/ar.json` bajo `admin.competitorBrands`
3. Usuario con rol "Comercial" no tiene `admin:read` → recibe el fallback con `t("noPermission")` (no tiene acceso)
4. Usuarios con rol "TI" o "Admin" tienen `admin:read` → ven "Marcas competidoras" en el sidebar bajo sección Administración
