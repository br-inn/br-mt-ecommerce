# Aprobación Traducción Árabe — MT Pricing

## Estado: PENDIENTE FIRMA

## Scope

Traducción completa de la interfaz MT Pricing al árabe (UAE Business Arabic).  
Cobertura: **858 claves** en 14 módulos de interfaz.

## Pantallas cubiertas

- Pantalla de login y restablecimiento de contraseña
- Catálogo de productos (lista + filtros avanzados + columnas)
- Detalle SKU + especificaciones técnicas + packaging
- Editor de traducciones EN/ES/AR por SKU (tab Traducciones)
- Galería de imágenes por SKU
- Recálculo de precio — Motor v5.1 (propuestas, filtros, columnas)
- Cola de aprobación del Gerente (bulk approve, review, detalle)
- Simulador what-if de precios
- Importador de hojas de cálculo PIM (wizard 4 pasos + reporte)
- Maestro de proveedores (lista, formulario, acciones)
- Cobertura de costes (dashboard de costes activos por esquema)
- Panel principal (KPIs, actividad reciente, calidad de datos)
- Admin: usuarios, jobs, imports, feature flags, calibrator
- Divisas y tasas FX

## Cobertura de claves

| Locale | Claves | Cobertura |
|--------|--------|-----------|
| es (fuente) | 858 | 100% |
| en | 858 | 100% |
| ar | 858 | 100% |

Verificado con `pnpm i18n:audit` (exit code 0).

## Validación RTL

- `dir="rtl"` en `<html>` root cuando locale=ar ✅  
  Implementado en `app/layout.tsx` mediante `localeDirection(locale)` desde `lib/i18n/config.ts`
- `RTL_LOCALES = ["ar"]` configurado en `lib/i18n/config.ts` ✅
- `isRtlLocale()` y `localeDirection()` disponibles en todo el proyecto ✅
- Tailwind logical properties (`ms-*`, `me-*` en lugar de `ml-*`, `mr-*`) — revisar componentes shell en code review

## Estilo lingüístico

Árabe de negocios formal del Golfo Pérsico (UAE / Emirates). Se han usado:
- Términos técnicos del dominio con contexto en árabe (ej. `رمز المنتج (SKU)`)
- Sustantivos plurales correctos para ICU MessageFormat (`=0`, `=1`, `other`)
- Direccionalidad de cotizaciones adaptada: `"من"` / `"إلى"` para pares de divisas
- Terminología de aprobaciones alineada con práctica empresarial UAE

## Instrucciones para el revisor

1. Ejecutar `pnpm i18n:audit` — debe reportar ✅ 100% en todos los locales
2. Navegar a `/ar/productos` y verificar que el texto se lee de derecha a izquierda
3. Verificar que los números (precios, SKUs, EANs) se muestran en formato occidental (0-9), no árabe-hindú — correcto para interfaces de negocio UAE
4. Revisar la cola de aprobación (`/ar/precios` → botón الاعتمادات) y verificar coherencia terminológica
5. Firmar abajo si la traducción es apropiada para el mercado UAE

## Firma

| Rol | Nombre | Firma | Fecha |
|-----|--------|-------|-------|
| Translation Owner | | | |
| PM | psierra | | 2026-05-12 |
