# Diseño — Admin UI: Scraper Sources (F1 Frontend)

- **Fecha:** 2026-05-23
- **Autor:** psierra (con asistencia de Claude)
- **Estado:** Aprobado — listo para implementación
- **Relacionado:** `2026-05-20-scraper-source-builder-design.md` (backend F1, ya en `main`)

---

## 1. Contexto

El backend F1 del Scraper Source Builder está completo y en `origin/main`:
- API REST `/api/v1/scraper-sources` (CRUD + validar + activar)
- Modelos `ScraperSource` + `ScraperSourceRecipe` + `ScraperSourceTestRun`
- Tarea Celery `mt.scraper.scrape_source`

Lo que falta es la UI de administración que permita a un usuario no técnico crear, configurar y validar sources de scraping genéricas sin tocar código.

---

## 2. Ruta y entrada de menú

**Ruta:** `/admin/scraper/sources`

**Sidebar** — añadir en `SECTION_SYS_ADMIN` de `components/shell/sidebar.tsx`:
```typescript
{ href: "/admin/scraper/sources", label: "Scraper Sources", icon: Rss, permissions: ["admin:read"] }
```

---

## 3. Layout — Master / Detail

Una sola ruta. La página se divide en dos paneles horizontales:

```
┌──────────────────────────────────────────────────────────────┐
│  Scraper Sources                           [+ Nueva Source]  │
├──────────────────────┬───────────────────────────────────────┤
│  LISTA (izq.)        │  DETALLE (der.)                       │
│                      │                                       │
│  shopee-uae  draft   │  <nombre source seleccionada>         │
│  amazon-3p   active  │  ┌─────────────────────────────────┐  │
│  noon-deals  testing │  │ [Info]  [Recipe]  [Validación]  │  │
│                      │  └─────────────────────────────────┘  │
│  (click → selecciona)│  <contenido del tab activo>           │
│                      │                                       │
│                      │  (vacío si ninguna seleccionada)      │
└──────────────────────┴───────────────────────────────────────┘
```

- Panel izquierdo: ~30% del ancho, lista con nombre + badge de `status`.
- Panel derecho: ~70%, muestra detalle de la source seleccionada.
- Sin navegación de página — todo en `/admin/scraper/sources`.
- Sin ninguna source seleccionada el panel derecho muestra un estado vacío ("Selecciona una source").

---

## 4. Panel izquierdo — Lista de Sources

### Datos mostrados por item
- Nombre (`name`)
- Badge de `status`: `draft` (gris) / `testing` (amarillo) / `active` (verde) / `disabled` (rojo) / `degraded` (naranja)

### Acciones en la lista
- Clic en item → selecciona y muestra detalle en panel derecho
- Botón **+ Nueva Source** (header): abre Dialog de creación

### Estado de carga
- Skeleton de 3 filas mientras `isLoading`
- Mensaje de error si falla la query

---

## 5. Tab Info

Muestra los campos de `ScraperSource`:

| Campo | Tipo | Notas |
|-------|------|-------|
| `name` | texto | display name |
| `slug` | texto | unique identifier, read-only tras crear |
| `base_url` | URL | validar formato URL |
| `destination_profile` | select | `competitor_price` \| `product_data` |
| `fetch_mode` | select | `static` (único soportado en F1) |
| `status` | select | `draft` / `testing` / `active` / `disabled` |

- Vista: campos en modo lectura con un botón **Editar**.
- Clic en **Editar** → Dialog con formulario (`react-hook-form` + `zod`).
- On success: `invalidateQueries` + toast "Source actualizada".

### Dialog "Nueva Source" / "Editar Source"
- Mismos campos excepto que `slug` es editable solo en creación.
- `fetch_mode` solo muestra `static` por ahora (F2/F3 añadirán headless/stealth).
- Validación: `base_url` debe ser URL válida, `name` y `slug` requeridos.

---

## 6. Tab Recipe

### Estado de la recipe activa
- Muestra la recipe con `is_live = true` (si existe).
- Badge visual indicando versión activa.
- JSON de la recipe renderizado en un `<pre>` read-only con fondo oscuro.

### Crear nueva versión
- Botón **+ Nueva versión**: Dialog con `<textarea>` pre-rellenado con el JSON de la recipe activa (fork).
- Si no hay recipe activa, pre-rellena con un template vacío:
  ```json
  {
    "url_templates": { "search": "", "pdp": "" },
    "list_item_selector": "",
    "fields": []
  }
  ```
- Guardar llama a `POST /scraper-sources/{id}/recipes`.
- On success: refetch recipes, toast "Recipe guardada".

### Lista de versiones anteriores
- Acordeón colapsado con las versiones no-live (máx. 5 mostradas).
- Cada versión muestra: número de versión, `created_at`, `validation_status`.

---

## 7. Tab Validación

Flujo en 3 estados:

### Estado inicial (idle)
- Input URL de prueba (placeholder: `https://...`)
- Selector de recipe (dropdown de versiones disponibles, pre-selecciona la activa)
- Botón **Probar** (deshabilitado si no hay URL)

### Estado ejecutando
- Spinner + texto "Validando…"
- Botón deshabilitado

### Estado resultado
- Tabla de campos con columnas: `campo` / `resultado` / `valor extraído`
- Icono ✓ verde (pass) o ✗ rojo (fail) por campo
- Si todos pasan: botón **Activar esta recipe** habilitado
- Si alguno falla: botón **Activar** deshabilitado + mensaje explicativo

### Activación
- Clic en **Activar** → `POST /scraper-sources/{id}/activate` (body: `{ recipe_id }`)
- On success: badge de status de la source cambia a `active`, toast "Recipe activada".

---

## 8. Archivos a crear / modificar

### Nuevos
| Archivo | Descripción |
|---------|-------------|
| `app/(app)/admin/scraper/sources/page.tsx` | Server component con metadata + RbacGuard |
| `app/(app)/admin/scraper/sources/_client.tsx` | Client component principal (layout master/detail + todos los dialogs) |
| `lib/hooks/admin/use-scraper-sources.ts` | React Query hooks (list, create, update, recipes, validate, activate) |
| `lib/api/endpoints/scraper-sources.ts` | API client tipado con `authedFetch` |

### Modificados
| Archivo | Cambio |
|---------|--------|
| `components/shell/sidebar.tsx` | +1 entrada en `SECTION_SYS_ADMIN` |

---

## 9. Tipos TypeScript

```typescript
// Mirrors backend Pydantic schemas
type ScraperSourceStatus = "draft" | "testing" | "active" | "disabled" | "degraded";
type FetchMode = "static" | "headless" | "stealth";
type DestinationProfile = "competitor_price" | "product_data";
type ValidationStatus = "unvalidated" | "passing" | "failing";

interface ScraperSourceRead {
  id: string;
  name: string;
  slug: string;
  base_url: string;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
  status: ScraperSourceStatus;
  created_at: string;
  updated_at: string;
}

interface ScraperSourceCreate {
  name: string;
  slug: string;
  base_url: string;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
}

interface ScraperSourceUpdate {
  name?: string;
  base_url?: string;
  destination_profile?: DestinationProfile;
  fetch_mode?: FetchMode;
  status?: ScraperSourceStatus;
}

interface RecipeRead {
  id: string;
  source_id: string;
  version: number;
  is_live: boolean;
  recipe: Record<string, unknown>;
  validation_status: ValidationStatus;
  created_at: string;
}

interface RecipeCreate {
  recipe: Record<string, unknown>;
}

interface ValidationResult {
  validation_status: ValidationStatus;
  fields: Array<{
    name: string;
    passed: boolean;
    value?: string;
    error?: string;
  }>;
}
```

---

## 10. React Query keys y staleTime

```typescript
const KEYS = {
  all: () => ["scraper-sources"] as const,
  list: () => [...KEYS.all(), "list"] as const,
  detail: (id: string) => [...KEYS.all(), "detail", id] as const,
  recipes: (id: string) => [...KEYS.all(), id, "recipes"] as const,
};
```

- `staleTime` lista: `30_000` ms
- `staleTime` detalle/recipes: `60_000` ms
- Validación: `staleTime: 0` (siempre fresca)

---

## 11. Permisos RBAC

- Página y sidebar: `admin:read`
- Crear/editar source y recipes: `admin:read` (misma guarda, el backend valida)
- No se añaden nuevos permisos al sistema

---

## 12. Lo que queda fuera (F2/F3)

- Modos `headless` y `stealth` en el selector `fetch_mode` (el backend lanza `NotImplementedError`)
- Editor visual de campos (structured form builder)
- Asistente LLM para proponer selectores automáticamente
- Historial de test runs en el tab Validación
