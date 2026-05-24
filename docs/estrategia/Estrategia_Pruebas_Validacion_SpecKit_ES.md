# Estrategia de Pruebas y Validación — br-mt-ecommerce

> **Encaje.** Este documento es la capa de pruebas de la Estrategia de Requisitos Funcionales Spec Kit V2 (`Estrategia_Requisitos_Funcionales_SpecKit_ES.docx`). Responde a una pregunta concreta: dentro de la estrategia, **cómo se cubren las pruebas, dónde se deja la información y cómo se revisa lo que se ha probado**. Se apoya en la infraestructura de pruebas que el repositorio **ya tiene** — no inventa una nueva.

- **Versión:** 1.0 (borrador) · pendiente de ratificación del equipo.
- **Fecha:** 2026-05-24.
- **Documentos hermanos:** [[F1-CAT_Plan_de_Pruebas]] · [[F1-CAT_Control_Piloto]] · constitución del proyecto (`.specify/memory/constitution.md`).

---

## 1. Principio rector

La estrategia Spec Kit produce, para cada proceso, una **spec** con requisitos
funcionales (`FR-<DOM>-NNN`), escenarios de aceptación (Given/When/Then) y criterios de
éxito medibles. La estrategia de pruebas cierra el círculo: **cada requisito debe poder
demostrarse**, y esa demostración debe quedar **registrada y ser revisable**.

> Un requisito sin prueba es una intención. Un requisito con prueba en verde es un hecho.

La verificación de F1 tiene **dos grados**, y el objetivo es subir todo lo posible del
primero al segundo:

1. **Verificación documental** — alguien lee el código y marca el FR como cumplido en la
   matriz. Es el punto de partida del piloto F1; es válida pero caduca: un cambio futuro
   puede romperla sin que nadie lo note.
2. **Prueba automatizada** — existe un test ejecutable anclado al FR. Se re-verifica solo
   en cada `push`. Es el estado objetivo.

## 2. Las cuatro capas de prueba

El repositorio ya tiene una pirámide de pruebas montada. La estrategia la **organiza en
cuatro capas** y nombra explícitamente la que faltaba (Capa 3).

```
        ╱ Capa 4 — Calidad del dato real ╲      el catálogo en producción
       ╱  Capa 3 — Pruebas de proceso     ╲     ¿cumple cada FR? (F1)
      ╱   Capa 2 — Pruebas e2e             ╲    journeys de usuario
     ╱    Capa 1 — Pruebas de desarrollo    ╲   unidad + integración
```

### Capa 1 — Pruebas de desarrollo (unidad + integración)

Las que escribe quien desarrolla, mientras desarrolla. Cubren lógica de negocio, casos
límite y contratos internos. **Ya existen y están maduras.**

| | Backend (`mt-pricing-backend`) | Frontend (`mt-pricing-frontend`) |
|---|---|---|
| Herramienta | pytest + pytest-asyncio + httpx + testcontainers | vitest |
| Volumen actual | ~243 archivos de test | ~43 archivos de test |
| Marcadores | `unit` (sin IO), `integration` (testcontainers Postgres/Redis/pgvector), `api` (integración a nivel ASGI) | — |
| Dónde viven | `mt-pricing-backend/tests/{unit,integration,api,db,services,...}/` | junto al componente, `*.test.tsx` |
| Cobertura | gate **≥ 70 %** backend (rama `--cov=app`, branch coverage) | sin gate numérico hoy |

**Qué cubrir:** lógica de servicio, validación de schemas Pydantic/Zod, repositorios,
transformaciones, casos de error. **Qué no:** getters triviales, código de framework.

### Capa 2 — Pruebas end-to-end (e2e)

Recorridos completos de usuario sobre la app real (navegador + API + DB). Dan la mayor
confianza y son las más lentas; por eso son pocas y cubren los *journeys* críticos.

- **Herramienta:** Playwright. **Ubicación:** `mt-pricing-frontend/tests/e2e/` (~19 specs
  numerados: `03-products-list`, `04-product-detail-edit`, `08-filtros-avanzados`, …).
- **Backend e2e:** marcador `e2e` en pytest (cliente ASGI de punta a punta).
- **Estado de automatización:** Playwright corre en `ci-frontend-full.yml` **detrás del
  flag `RUN_PLAYWRIGHT=true`, hoy en `false`**. > **NOTA AL EQUIPO:** decidir cuándo se
  activa como gate bloqueante (recomendación §6).

### Capa 3 — Pruebas de proceso / verificación de aceptación  *(la capa F1)*

**Esta es la capa que la estrategia añade.** No es una herramienta nueva: es el **puente
entre la spec y las Capas 1–2**. Por cada `FR-<DOM>-NNN` de la spec de un proceso, su
escenario de aceptación Given/When/Then se materializa en **un test ejecutable**:

- Si el FR es una regla de backend o un contrato de API → test con marcador `api`.
- Si el FR es un *journey* de usuario → spec de Playwright (Capa 2).
- Si el FR es lógica pura → test `unit`.

La diferencia con la Capa 1 no es técnica sino de **trazabilidad**: un test de proceso
**está anclado a un FR** — su nombre y su docstring citan el ID (`FR-CAT-007`), y la
matriz de trazabilidad (§5) enlaza FR ↔ test.
Convención propuesta: archivo `test_<proceso>_acceptance.py` y un marcador pytest nuevo
`acceptance` para poder correr el conjunto de un proceso de una vez.

Mientras un FR no tenga test, su verificación es **documental** (grado 1) y se registra
en el `verification.md` del proceso. El trabajo de F1 es ir cerrando esa brecha.

### Capa 4 — Validación de la calidad del dato real

Las Capas 1–3 prueban que **el código** hace lo correcto. La Capa 4 prueba que **los
datos del catálogo en producción** son correctos — algo que ningún test de código
detecta. Es una validación continua, no un test de regresión.

- **Instrumento (ya existe):** `GET /admin/pim/data-quality` (`admin_pim_quality.py`).
  Diagnostica el catálogo PIM y reporta, con porcentaje y SKUs de muestra:
  `missing_name_en`, `missing_specs`, `missing_images`, `missing_brand`,
  `missing_family`, `specs_below_threshold` (< 3 claves en `specs`).
- **Señal complementaria:** el campo `data_quality` del producto
  (`complete` / `partial` / `blocked` / `migrated_demo`). `migrated_demo` marca dato de
  demo, no real: en producción su objetivo es **0 %**.
- **Umbrales:** los fija el equipo por dominio (ver [[F1-CAT_Plan_de_Pruebas]] para CAT).
  El reporte es el termómetro; los umbrales convierten el termómetro en semáforo.
- **Cadencia:** un **job programado** (Celery, fila en `public.job_definitions` — nunca
  hardcodeado, ver constitución Art. 1) toma una instantánea periódica del reporte y la
  archiva. Así se ve la **tendencia**, no solo la foto.

## 3. Del requisito a la prueba — el flujo

Cómo una spec de proceso se convierte en pruebas, paso a paso:

1. **Spec** (`/speckit.specify`) — define `FR-<DOM>-NNN` con escenarios Given/When/Then
   verificables y criterios de éxito `SC-NNN` medibles.
2. **Verificación documental** (F1, Capa 3, grado 1) — se contrasta cada FR contra el
   código; se clasifica `Verificado / Parcial / No cumple / No implementado` en el
   `verification.md` del proceso.
3. **Automatización** (Capa 3, grado 2) — cada FR engendra un test (Capa 1 o 2). Las
   brechas (`Parcial / No cumple / No implementado`) se vuelven issues; el test puede
   nacer en `xfail` documentando el defecto hasta que se corrija.
4. **Registro** — el FR, su estado y su(s) test(s) se enlazan en la matriz de
   trazabilidad. La spec no está "hecha" hasta que la matriz lo refleja.
5. **Regresión continua** — a partir de ahí, cada `push` re-verifica el FR gratis vía CI.

> **F1 verifica; no remedia.** La verificación y la escritura de pruebas no corrigen
> bugs de la aplicación. Un test que destapa un defecto **lo documenta** (issue + `xfail`);
> la corrección es trabajo posterior, priorizado aparte.

## 4. Definición de Hecho de pruebas

Amplía el Artículo 7 de la constitución ("proceso hecho: criterios de aceptación
verificados; pruebas en verde; matriz a Verificado"). Un proceso está **probado** cuando:

- [ ] Cada FR de prioridad **P1 y P2** tiene al menos un test automatizado anclado a su ID.
- [ ] Cada endpoint en alcance tiene al menos un caso *happy* y uno *unhappy*.
- [ ] La suite completa pasa en verde en CI; el gate de cobertura (**≥ 70 % backend**) se respeta.
- [ ] Los *journeys* P1 del proceso tienen cobertura e2e (Playwright).
- [ ] El reporte de calidad de dato del dominio cumple los umbrales acordados.
- [ ] La matriz de trazabilidad está actualizada: FR ↔ implementación ↔ test ↔ estado.
- [ ] Las brechas conocidas están abiertas como issues, no silenciadas.

> **NOTA AL EQUIPO:** se recomienda incorporar esta Definición de Hecho como un
> **artículo de pruebas explícito** en la constitución (enmienda según Art. 8).

## 5. Dónde se deja la información de prueba

Mapa único de ubicaciones. Todo artefacto de prueba tiene **un sitio y solo uno**.

| Artefacto | Ubicación | Formato |
|-----------|-----------|---------|
| Tests de desarrollo backend | `mt-pricing-backend/tests/` (marcadores `unit`/`integration`/`api`) | código pytest |
| Tests de desarrollo frontend | junto al componente, `*.test.tsx` | código vitest |
| Tests de proceso (Capa 3) | `tests/.../test_<proceso>_acceptance.py`, marcador `acceptance`; docstring cita el FR | código pytest |
| Tests e2e | `mt-pricing-frontend/tests/e2e/*.spec.ts` | código Playwright |
| Reporte de cobertura | artefacto de CI (`coverage.xml`) + `term-missing` en el log del job | XML / log |
| Reporte de ejecución e2e | `mt-pricing-frontend/playwright-report/`, `test-results/` | HTML |
| Verificación de proceso | `specs/NNN-<dom>-<slug>/verification.md` | markdown (en el repo) |
| Trazabilidad por proceso | `specs/NNN-<dom>-<slug>/traceability-<dom>.csv` | CSV (en el repo) |
| **Matriz maestra de trazabilidad** | `Matriz_Trazabilidad_Verificacion_SpecKit.xlsx` | XLSX — estado por FR de todos los procesos |
| Instantáneas de calidad de dato | `MT-ME\F1-Control\calidad-dato\YYYY-MM-DD.md` | markdown (archivado del job) |
| Control y revisión | `MT-ME\F1-Control\` | markdown (Cowork) |

La **matriz maestra** es la espina dorsal: es donde se revisa "qué se ha probado". Su
modelo de columnas extiende el del [[F1-CAT_Control_Piloto]] con dos columnas nuevas que
aporta esta estrategia — `FR_ID · Descripción · Origen · Endpoint/Componente ·
Estado verificación · Evidencia · **Prueba(s) automatizada(s)** · **Estado de prueba** ·
Brecha/Notas`.

> **NOTA AL EQUIPO:** la matriz maestra aún no tiene hogar estable. Decisión pendiente:
> versionarla en el repo (`specs/_matriz/`) o mantenerla en `MT-ME\F1-Control\`.

## 6. Cómo revisa el usuario lo que se ha probado

Cuatro puntos de revisión, de lo inmediato a lo panorámico. **Ninguno exige leer código.**

1. **En el Pull Request — los checks de CI.** Verde o rojo, al instante: `lint`,
   `typecheck`, `tests + cobertura`, `security`, `build`, y (cuando se active) `e2e`.
   `pr-checks.yml` además exige que la descripción del PR traiga su sección
   **`## Test plan`** rellena. Es la revisión del *cambio concreto*.
2. **En la matriz de trazabilidad — el estado por FR.** Responde "¿qué porcentaje del
   proceso está verificado y con prueba automatizada?". Es la revisión del *proceso*.
3. **En el `verification.md` del proceso — el detalle.** Cada FR con su estado, su
   evidencia (`archivo:línea`) y su brecha. Es la revisión *forense*, cuando algo no cuadra.
4. **En la instantánea de calidad de dato — el catálogo real.** El reporte archivado
   muestra si los datos de producción cumplen umbrales y hacia dónde tienden. Es la
   revisión del *dato*, no del código.

> **Opción — panel en vivo.** Estos cuatro puntos pueden consolidarse en un panel
> (artefacto Cowork) que lea el estado de la matriz y de CI en cada apertura. Es
> opcional; se ofrece cuando el primer proceso esté verificado y haya datos que mostrar.

## 7. Automatización — los gates de CI

Qué corre, cuándo, y qué **bloquea el merge**.

| Workflow | Dispara | Contenido | ¿Bloquea? |
|----------|---------|-----------|:--------:|
| `ci-backend.yml` | PR / push | lint (ruff) · typecheck (mypy) · pytest + cobertura · pip-audit · build | **Sí** (gate base) |
| `ci-frontend.yml` | PR / push | lint · typecheck · vitest · build + bundle size | **Sí** (gate base) |
| `pr-checks.yml` | PR | commitlint · título semántico · plantilla con `## Test plan` · labels | **Sí** |
| `ci-backend-full.yml` | PR / push a `main` (paths backend) | suite completa + integration sobre Postgres/Redis/pgvector + Alembic | Sí en paths backend |
| `ci-frontend-full.yml` | PR / push a `main` (paths frontend) | tsc · eslint · vitest · **Playwright tras `RUN_PLAYWRIGHT`** | e2e **aún no** |
| `codeql.yml` · `secrets-scan.yml` | PR / programado | análisis estático de seguridad · fuga de secretos | Sí |
| **Job de calidad de dato** *(a crear)* | programado (Celery beat) | snapshot de `GET /admin/pim/data-quality` → archivo | No bloquea; alerta |

**Recomendaciones de automatización:**

- **R-A1.** Activar `RUN_PLAYWRIGHT=true` y hacer e2e **bloqueante por proceso**: en
  cuanto un proceso F1 quede verificado y su set de specs e2e sea estable, sus journeys
  P1 pasan a gate. Empezar por el proceso piloto CAT.
- **R-A2.** Marcador `acceptance` en pytest para los tests de proceso (Capa 3), de modo
  que `pytest -m acceptance` corra la verificación de un proceso completa.
- **R-A3.** Crear el **job programado de calidad de dato** (Celery, fila en
  `public.job_definitions`) que archive la instantánea en `MT-ME\F1-Control\calidad-dato\`.
  Cadencia inicial sugerida: semanal.
- **R-A4.** Subir progresivamente el gate de cobertura del **70 %** actual conforme F1
  cierre brechas (la auditoría BMAD reportó 62 % de endpoints del módulo de productos sin
  test); no bajarlo nunca.

## 8. Hoja de ruta de adopción

| Estado | Elemento |
|:------:|----------|
| ✅ Ya existe | Capa 1 (pytest, vitest, testcontainers, ~286 archivos de test), gates base de CI, gate de cobertura 70 %, plantilla de PR con `## Test plan`, instrumento de calidad de dato `GET /admin/pim/data-quality` |
| 🟡 Parcial | Capa 2 e2e (specs escritas, pero Playwright no es gate); cobertura desigual (62 % de endpoints de productos sin test) |
| 🔴 A construir | Capa 3 formalizada (tests anclados a FR + marcador `acceptance`); columnas FR↔test en la matriz; job programado de calidad de dato; e2e como gate |

**Secuencia:** el proceso piloto **CAT** recorre las cuatro capas de punta a punta y
sirve de plantilla — ver [[F1-CAT_Plan_de_Pruebas]]. Lo que funcione en CAT se
estandariza y se replica en los ~24 procesos de la cola F1.

## 9. Notas y decisiones abiertas

> **NOTA 1 — Artículo de pruebas en la constitución.** Incorporar la Definición de Hecho
> de pruebas (§4) como artículo formal (enmienda Art. 8).

> **NOTA 2 — e2e como gate.** Decidir el momento de activar `RUN_PLAYWRIGHT=true` de
> forma bloqueante (recomendación R-A1: por proceso, empezando por CAT).

> **NOTA 3 — Hogar de la matriz maestra.** Pendiente: repo (`specs/_matriz/`) vs
> `MT-ME\F1-Control\`. Hasta resolverlo, la fuente por proceso es el `traceability-<dom>.csv`.

> **NOTA 4 — Umbrales de calidad de dato.** El equipo debe fijar, por dominio, los
> umbrales del reporte PIM (p. ej. `migrated_demo = 0 %`, `missing_specs ≤ X %`).

> **NOTA 5 — Cobertura del frontend.** Hoy no hay gate numérico de cobertura en el
> frontend; valorar añadir uno cuando vitest cubra los componentes de los procesos F1.

---

### Enlaces

- Plan aplicado al piloto: [[F1-CAT_Plan_de_Pruebas]]
- Control del piloto: [[F1-CAT_Control_Piloto]]
- Prompt de ejecución de pruebas: `MT-ME\_INBOX\Prompt_ClaudeCode_F1_CAT_Pruebas_ES.md`
- Constitución: `br-mt-ecommerce\.specify\memory\constitution.md`
