# Spec retrospectiva: Compatibilidad y Variantes (sub-recurso CAT)

**Feature Branch**: `docs/f1-compatibilidad-variantes`

**Creado**: 2026-05-25

**Tipo**: Retrospectivo — documenta el comportamiento ACTUAL del sistema, no funcionalidad futura.

**Dominio**: CAT — sub-recurso: Compatibilidad M:N y Display Pair

**Nota importante**: FR-CAT-033..035 (jerarquía padre/hijo, prevención de ciclos, profundidad=1)
ya están verificados en `specs/001-cat-gestion-catalogo-productos/verification.md` Área 12.
Este spec cubre el alcance adicional: compatibilidades M:N entre productos, display pair simétrico,
y el servicio de effective display (tags + certificaciones efectivos).

---

## Clarificaciones

### Sesión 2026-05-25

- Q: ¿El display pair implica bidireccionalidad automática? → A: Sí. `set_pair(A, B)` actualiza
  `display_pair_sku` en ambas direcciones dentro de una única transacción. Si A tenía pareja previa
  distinta, esa pareja queda con `NULL` (limpieza simétrica). Evidencia: `display_pair_service.py:42-73`.
- Q: ¿La compatibilidad M:N es unidireccional o bidireccional? → A: Unidireccional salvo para los
  pares semánticos `replaces`/`replaced_by`, que el repo sincroniza automáticamente al insertar o
  eliminar. Los demás tipos (`spare_part`, `accessory`, `compatible_with`) son estrictamente
  unidireccionales. Evidencia: `compatibility.py (repo):24-27` + `add_link:129-147`.
- Q: ¿`effective-display` usa `products.tags`? → A: No. `products.tags` fue eliminado en Fase B
  (mig. 065). `EffectiveDisplayService` usa sólo `series.features_tags` para tags y une
  `series_certifications` + `product_certifications` para certs. Evidencia: `effective_display_service.py:76-117`.

---

## Escenarios de usuario y prueba

### Historia 1 — Gestión de recambios y accesorios del catálogo (P1)

El gestor de catálogo (Comercial) necesita documentar qué productos son recambios,
accesorios o sustituciones de otros. También quiere saber qué otros productos hacen
referencia a un SKU dado (vista inversa).

**Casos de aceptación**:

1. **Dado** que soy Comercial con permiso `products:write`,
   **Cuando** envío `POST /products/{sku}/compatibility` con `{compatible_with_sku, kind: "spare_part"}`,
   **Entonces** el sistema crea el enlace, emite auditoría `compatibility.add`, devuelve HTTP 201
   con el enlace desnormalizado (sku, name_en, family del destino).

2. **Dado** que soy Comercial con permiso `products:read`,
   **Cuando** consulto `GET /products/{sku}/compatibility/inverse`,
   **Entonces** recibo los enlaces donde este SKU es el producto DESTINO
   (¿qué productos tienen este SKU como recambio?).

3. **Dado** que añado `A → replaces → B`,
   **Entonces** el sistema crea automáticamente el inverso `B → replaced_by → A`
   sin intervención del usuario.

### Historia 2 — Emparejamiento de color (display pair) (P2)

El merchandiser quiere presentar dos variantes de color de un mismo modelo como
un par visual en la tienda (ej: válvula roja 4295 ↔ válvula azul 42952).

**Casos de aceptación**:

1. **Dado** que envío `PUT /products/{sku}/display-pair` con `{paired_sku}`,
   **Entonces** ambos SKUs quedan enlazados simétricamente y cualquier pareja previa
   de cualquiera de los dos queda limpiada.

2. **Dado** que envío `DELETE /products/{sku}/display-pair`,
   **Entonces** el enlace de ambos lados (sku y su partner) queda a NULL.

3. **Dado** que intento enlazar un SKU consigo mismo,
   **Entonces** recibo HTTP 400 `display_pair_self`.

### Historia 3 — Vista efectiva de tags y certificaciones (P2)

El frontend de producto necesita renderizar los tags de características y las
certificaciones del producto combinando las que hereda de su serie con las
específicas del SKU individual.

**Casos de aceptación**:

1. **Dado** que consulto `GET /products/{sku}/effective-display`,
   **Entonces** recibo `{tags, certifications}` donde tags viene de `series.features_tags`
   y certifications es la unión dedup de overrides del producto + defaults de la serie
   (los overrides del producto tienen precedencia).

2. **Dado** que el SKU no existe,
   **Entonces** recibo HTTP 404.

---

## Requisitos funcionales

### FR-CPT-001 — Listado de compatibilidades outgoing

El sistema DEBE exponer `GET /products/{sku}/compatibility` que devuelva los enlaces
donde `sku` es el producto origen (outgoing). Soporta filtro opcional por `kind`.

**Evidencia**: `products.py:1402-1423` + `compatibility_service.py:96-103`.

---

### FR-CPT-002 — Listado de compatibilidades incoming (vista inversa)

El sistema DEBE exponer `GET /products/{sku}/compatibility/inverse` que devuelva los
enlaces donde `sku` es el producto destino. Soporta filtro opcional por `kind`.

**Evidencia**: `products.py:1426-1462` + `compatibility_service.py:105-112`.

---

### FR-CPT-003 — Alta de enlace de compatibilidad

El sistema DEBE exponer `POST /products/{sku}/compatibility` que cree un enlace
`sku → kind → compatible_with_sku`. Validaciones: ambos SKUs deben existir, no
auto-enlace, no duplicado `(product_sku, compatible_with_sku, kind)`.

**Evidencia**: `products.py:1465-1502` + `compatibility_service.py:116-185`.

---

### FR-CPT-004 — Baja de enlace de compatibilidad

El sistema DEBE exponer `DELETE /products/{sku}/compatibility/{compatible_with_sku}/{kind}`
que elimine el enlace exacto identificado por los tres parámetros. Devuelve HTTP 204.
Si no existe, HTTP 404.

**Evidencia**: `products.py:1505-1534` + `compatibility_service.py:187-215`.

---

### FR-CPT-005 — Reemplazo bulk de compatibilidades

El sistema DEBE exponer `PUT /products/{sku}/compatibility` que reemplace TODOS los
enlaces outgoing del SKU con la lista del body. Body vacío `[]` elimina todas las
compatibilidades. Incluye validación pre-reemplazo de todos los destinos.

**Evidencia**: `products.py:1537-1579` + `compatibility_service.py:217-266`.

---

### FR-CPT-006 — Tipos de compatibilidad soportados

El sistema DEBE soportar exactamente 5 `kind` values: `spare_part`, `accessory`,
`replaces`, `replaced_by`, `compatible_with`. Definidos como `CompatibilityKind` enum.
Cualquier otro valor → HTTP 422 por validación Pydantic.

**Evidencia**: `schemas/compatibility.py:20-28`.

---

### FR-CPT-007 — Sincronización automática replaces/replaced_by

Al añadir `A → replaces → B`, el repo DEBE crear automáticamente `B → replaced_by → A`
si no existe. Al eliminar `A → replaces → B`, el repo DEBE eliminar también
`B → replaced_by → A`. Esta sincronización ocurre sin intervención del caller.

**Evidencia**: `repositories/compatibility.py:24-27` (_INVERSE map) + `add_link:129-147`
+ `remove_link:170-181`.

---

### FR-CPT-008 — Desnormalización del producto destino en la respuesta

Al listar compatibilidades outgoing, cada enlace DEBE incluir un objeto
`compatible_product` con `{sku, name_en, family, primary_image_url}` del SKU destino
para evitar N+1 en la UI.

**Evidencia**: `products.py:1372-1399` (`_build_compat_response`) + `repositories/compatibility.py:48`
(`selectinload(ProductCompatibility.compatible_with)`).

---

### FR-CPT-009 — Filtro DN polimórfico para recambios de serie (Fase 5)

El sistema DEBE exponer `GET /vocabularies/series/{series_id}/spare-parts` con
parámetro opcional `dn` (entero 0..10000) que filtre recambios vinculados a una serie
completa (`owner_type='series'`) dentro de un rango DN concreto:
`(dn_min IS NULL OR dn_min <= dn) AND (dn_max IS NULL OR dn_max >= dn)`.

**Evidencia**: `taxonomy_extras.py:225-274` + `repositories/compatibility.py:238-278`.

---

### FR-CPT-010 — Display pair: establecimiento simétrico

El sistema DEBE exponer `PUT /products/{sku}/display-pair` que enlace `sku` a
`paired_sku` simétricamente. Si alguno tenía pareja previa distinta, esa pareja
queda con `display_pair_sku = NULL` (limpieza simétrica). Operación en transacción única.
Auto-enlace → HTTP 400 `display_pair_self`.

**Evidencia**: `products_display.py:84-103` + `display_pair_service.py:42-73`.

---

### FR-CPT-011 — Display pair: limpieza simétrica (idempotente)

El sistema DEBE exponer `DELETE /products/{sku}/display-pair` que nullifique
`display_pair_sku` en ambos lados (sku y su partner actual). Si el SKU no tiene
pareja activa, la operación es no-op (idempotente). Devuelve HTTP 204.

**Evidencia**: `products_display.py:106-121` + `display_pair_service.py:75-88`.

---

### FR-CPT-012 — Effective display: tags y certificaciones efectivos

El sistema DEBE exponer `GET /products/{sku}/effective-display` que devuelva
`{tags: list[str], certifications: list[CertificationRef]}` calculados como:

- `tags`: lista de `series.features_tags` (campo `products.tags` eliminado en mig. 065).
- `certifications`: union dedup por `cert.code` de `product_certifications` (overrides,
  mayor precedencia) + `series.series_certifications` (defaults de serie, complemento).

**Evidencia**: `effective_display_service.py:76-117` + `products_display.py:63-81`.

---

## Requisitos no funcionales

### NFR-CPT-001 — RBAC por operación

- Lecturas (GET): `products:read`.
- Escrituras (POST, PUT, DELETE): `products:write`.
- Validación presente en todos los endpoints.

**Evidencia**: `products_display.py:71,97,111` + `products.py:1411,1435,1479,1517,1551`.

---

### NFR-CPT-002 — Sin N+1 en listado de compatibilidades

El listado outgoing DEBE usar `selectinload(ProductCompatibility.compatible_with)`
para cargar el producto destino en una sola query batch, no en N queries individuales.

**Evidencia**: `repositories/compatibility.py:48` (`selectinload(ProductCompatibility.compatible_with)`).

---

### NFR-CPT-003 — Sin N+1 en effective display

`EffectiveDisplayService.compute` DEBE cargar certificaciones de producto y serie
con `selectinload` para evitar lazy-load. El servicio hace 2-3 queries fijas
independientemente del número de certs (no N+1).

**Evidencia**: `effective_display_service.py:52-74` (selectinload en ambas queries).

---

### NFR-CPT-004 — Formato de error

Los endpoints de compatibilidad en `products.py` DEBEN usar `_raise_compat` que genera
ProblemDetails con campos `type`, `title`, `status`, `code` (más completo que `_raise_domain`
del spec núcleo CAT). Los endpoints de display en `products_display.py` usan
`_raise_domain` local con campos `title`, `status`, `type`.

**Evidencia**: `products.py:173-182` + `products_display.py:53-57`.

---

## Reglas de negocio

### BR-CPT-001 — No auto-enlace de compatibilidad

Un producto NO PUEDE ser compatible consigo mismo. Validado en dos niveles:
servicio (`compatibility_service.py:140-141`) y DB CHECK
(`chk_no_self_compatibility`: `product_sku <> compatible_with_sku`).

---

### BR-CPT-002 — No duplicados de compatibilidad

El trío `(product_sku, compatible_with_sku, kind)` es único. Constraint:
`uq_product_compatibility`. Violación → HTTP 409 `compatibility_duplicate`.

**Evidencia**: `db/models/compatibility.py:116-120` + `compatibility_service.py:165-166`.

---

### BR-CPT-003 — Compatibilidad M:N unidireccional por diseño

Salvo `replaces`/`replaced_by`, la compatibilidad es INTENCIONALMENTE unidireccional.
La vista inversa se resuelve por consulta, no por fila duplicada.

**Evidencia**: `db/models/compatibility.py:8-14` (docstring).

---

### BR-CPT-004 — Display pair: relación 1:1 simétrica

Cada producto puede tener como máximo UN display pair (campo escalar
`products.display_pair_sku`). Al establecer una nueva pareja, cualquier pareja previa
de cualquiera de los dos SKUs queda limpiada automáticamente.

**Evidencia**: `product.py:194-198` + `display_pair_service.py:53-64`.

---

### BR-CPT-005 — Compatibilidad DN-acotada para series

Los enlaces de tipo `owner_type='series'` soportan `dn_min`/`dn_max` para acotar
el rango de calibres aplicable. Si ambos son NULL, el enlace aplica a cualquier
calibre. Si `dn_max < dn_min` → HTTP 422 `compatibility_dn_range_invalid`.

**Evidencia**: `db/models/compatibility.py:74-77` + `compatibility_service.py:146-151`.

---

### BR-CPT-006 — Auditoría de mutaciones de compatibilidad

Toda operación de add/remove/replace_all emite un evento de auditoría con
`entity_type="product_compatibility"`, `action` y el snapshot antes/después.
El display pair NO emite auditoría (servicio sin AuditRepository).

**Evidencia**: `compatibility_service.py:168-184` (add), `:204-215` (remove),
`:258-265` (replace_all). Ausencia: `display_pair_service.py` no importa AuditRepository.

---

### BR-CPT-007 — Tags de productos: campo eliminado en Fase B

`products.tags` fue eliminado en migración 065 (Fase B). La hybrid property
`Product.tags` siempre devuelve lista vacía. `EffectiveDisplayService` usa
`series.features_tags` en su lugar. Cualquier código que lea `product.tags`
obtiene `[]` silenciosamente.

**Evidencia**: `product.py:412-421` (hybrid property con comentario).
