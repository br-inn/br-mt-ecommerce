# US-ERP-01-06 — Inline Edit Mode

**Sprint:** S14 | **Story Points:** 8 | **Status:** review | **Fecha:** 2026-05-16

## Resumen de implementación

### ProductHeader — Inline Edit Mode (UX-09)

**Archivo:** `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`

Mejoras implementadas sobre la versión preexistente:

#### Toggle Editar / Ver
- Botón "Editar" en header protegido con `RbacGuard permissions={["products:write"]}`
- Toggle `editMode` state (bool) + `draft` state con campos editables

#### Campos editables in-place (modo edición)
- **Nombre ES** (`draft.name_es`): `<Input>` inline que reemplaza el `<h1>` del título
- **Marca** (`draft.brand`): `<Input>` en Quick Facts
- **GTIN** (`draft.gtin`): `<Input>` monospace con `maxLength={14}` en Quick Facts
- **Estado del ciclo de vida** (`draft.lifecycle_status`): `<Select>` en la barra de badges

#### Botones Guardar / Descartar
- Aparecen en el header durante modo edición
- "Guardar" deshabilitado mientras `patchMutation.isPending`
- "Descartar" restaura los valores originales sin llamada al servidor

#### PATCH con dirty-fields only
- Solo se envían campos que cambiaron respecto al original
- `lifecycle_status` siempre incluido (campo de control)
- `brand` y `gtin` solo si difieren del original
- `translations.es.name` solo si `name_es` cambió y no está vacío

#### Toast de feedback (sonner)
- `toast.success(t("edit.success"))` en `onSuccess`
- `toast.error(t("errors.saveFailed"))` en `onError`
- `Toaster` ya está provisionado en el root layout

### i18n

Nuevas keys añadidas en `es.json`, `en.json`, `ar.json` bajo `catalog.product.inlineEdit`:
- `edit` — label del botón "Editar"
- `save` — label del botón "Guardar"
- `cancel` — label del botón "Descartar"
- `nameLabel` — aria-label del input de nombre
- `namePlaceholder` — placeholder del input de nombre

## ACs verificados

- [x] Toggle "Editar / Ver" en header con guard `products:write`
- [x] Campos editables in-place: nombre ES, marca, GTIN, lifecycle_status
- [x] Botones "Guardar" y "Descartar" visibles en modo edición
- [x] PATCH al endpoint `/api/v1/products/{sku}` con dirty fields
- [x] Sin recarga de página completa (React Query invalidate + state reset)
- [x] Toast de éxito y error con `sonner`
- [x] Al descartar: restaura valores originales sin llamada al servidor
- [x] i18n en ES / EN / AR
