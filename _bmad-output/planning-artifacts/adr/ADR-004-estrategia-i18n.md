# ADR-004: Estrategia i18n (canónico EN + traducciones ES/AR)

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT

## Contexto

MT Middle East necesita catálogo en tres idiomas:
- **EN** — idioma de mercado primario UAE/GCC, base para Amazon UAE / Noon UAE.
- **ES** — idioma de equipo MT España + algunos colaboradores internos.
- **AR** — idioma legal/marketing GCC, contenido para export a marketplaces y storefront B2C Fase 3.

El Excel actual tiene esto disperso en sheets paralelos (`PIM IDIOMAS`, `PIM Maestro`, `PIM + Catálogo MERGED`) → riesgo de descoordinación.

UI interna: español + inglés (selector de usuario interno MT). Sin RTL en Fase 1 (AR es contenido, no chrome de UI).

## Decisión

### Almacenamiento de datos

**Patrón "canónico + tabla de traducciones"**:

- Tabla `products` tiene un único `name_en NOT NULL` como **canónico**. EN es la lingua franca del mercado UAE, y forzar canónico previene "nadie sabe cuál es la versión correcta".
- Otros campos largos canónicos: `description_en`, `marketing_copy_en` (todos NOT NULL en EN).
- Specs técnicas (DN, PN, material, type, family) son **independientes de idioma** — códigos ISO o vocabularios controlados. Se localizan en UI con i18n keys, no en DB.
- Tabla `product_translations` (one-to-many SKU × lang):
  - `sku FK → products.sku`
  - `lang ENUM('es','ar')`
  - `name`, `description`, `marketing_copy` (cualquier campo localizable)
  - `status ENUM('pending','draft','approved')`
  - `translated_by`, `translated_at`, `reviewed_by`, `reviewed_at`
  - PK compuesta `(sku, lang)`.
- **Sólo ES y AR** en `product_translations`. EN nunca está aquí (vive en `products`).
- Estado de traducción `pending` → `draft` → `approved` por SKU/idioma. **Regla dura**: para que un SKU se publique en un canal que requiera AR (ej. Noon UAE storefront), su `(sku, 'ar').status` debe ser `approved`.

### UI interna

- **next-intl** como librería de i18n del frontend.
- Locales soportados UI: `es`, `en`. Default: `es` (idioma de trabajo declarado).
- Sin RTL Fase 1.
- Fichero de mensajes por locale en `src/messages/{locale}.json`, namespacing por feature.

### Workflow de traducción

1. Comercial crea SKU con `name_en` (canónico).
2. Sistema crea automáticamente filas `product_translations` con `lang IN ('es','ar')` y `status='pending'`.
3. Comercial llena ES (puede ser él mismo o delegado).
4. AR puede ser:
   - manual por colaborador AR-speaking,
   - import en bulk (CSV / XLSX) por idioma vía importer dedicado,
   - integración futura con servicio de traducción (DeepL, GPT-4 — Fase 1.5+).
5. Estado pasa `pending → draft → approved` por revisión humana.
6. Gerente Comercial puede ver "cobertura de traducción" como métrica en dashboard (objetivo: 100 % EN, ≥ 95 % ES y AR en SKUs publicables).

### Export por idioma

- API endpoint `GET /api/exports/products?lang=ar&channel=noon_uae` devuelve sólo SKUs con traducción AR `approved` + estados de canal compatibles + precios `approved | auto_approved`.

## Alternativas evaluadas

### Alternativa A: Una columna `name_es / name_en / name_ar` en `products` (denormalizado)
- **Pros**: queries más simples (un único JOIN).
- **Contras**: añadir un cuarto idioma (Fase 4 GCC: tal vez urdu, hindi, francés) requiere ALTER TABLE. Estado de traducción por idioma se vuelve `name_es_status`, `name_ar_status` → multiplica columnas. No escala.
- **Veredicto**: descartada por inflexibilidad.

### Alternativa B: JSONB con `{en: ..., es: ..., ar: ...}` en una sola columna
- **Pros**: flexibilidad de schema.
- **Contras**: pierde NOT NULL constraint sobre EN canónico, índices más caros, validación dispersa, audit trail más opaco (qué cambió: el nombre o el idioma?).
- **Veredicto**: descartada.

### Alternativa C: ES como canónico (lengua de la empresa)
- **Pros**: equipo MT trabaja en español.
- **Contras**: el mercado, los marketplaces, los compradores Amazon UAE / Noon UAE consumen EN o AR. Forzar ES como canónico obliga a traducir hacia EN cada SKU para publicar. Es un trabajo adicional duplicado.
- **Veredicto**: descartada. EN gana por mercado.

## Consecuencias positivas

- Estado de traducción explícito por idioma → métrica directa.
- Añadir un cuarto idioma = 0 ALTER TABLE, sólo nuevas filas.
- Audit trail granular (qué SKU, qué idioma, quién, cuándo).
- Constraint a nivel DB sobre canales que exigen AR → no hay forma de publicar AR vacío "por error".

## Consecuencias negativas / riesgos

- Cada query de listado público requiere LEFT JOIN `product_translations` + filtro por `lang` + `status='approved'`. Mitigación: vista materializada o función `product_publishable(sku, lang, channel)`.
- Costo de mantenimiento traducciones AR si no hay AR-speaker dedicado. Mitigación: bulk import + traducción asistida con LLM Fase 1.5+ (revisión humana siempre).

## Cuándo revisar

- **Cierre Fase 1a**: validar que la cobertura de traducción AR llega al objetivo (≥ 95 %) y si no, decidir feature de traducción asistida o trabajar con vendor de traducción.
- **Fase 4**: añadir locales GCC adicionales según mercados objetivo.
- **Fase 3 storefront**: si el storefront B2C UAE requiere RTL UI completo, abrir issue de UI separado.
