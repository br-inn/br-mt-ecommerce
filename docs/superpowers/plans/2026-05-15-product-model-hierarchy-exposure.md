# Product Model Hierarchy Exposure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer la jerarquía `product_models` (mig 126-130) en el API y en la página `/catalogo/[sku]`, incluyendo certificados, coeficientes de flujo, y campos de grado de material.

**Architecture:** Las migraciones 126-130 ya existen en DB. El backend necesita 5 cambios (schemas + repo + endpoints) y el frontend 4 cambios (types + header + components + page). Backend y frontend son independientes entre sí y pueden ejecutarse en paralelo.

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 async (backend) · Next.js 16 + React 19 + TypeScript + React Query (frontend)

---

## Árbol de archivos

```
BACKEND — modificar:
  mt-pricing-backend/app/schemas/vocabularies.py           ← SeriesResponse +3 campos
  mt-pricing-backend/app/schemas/components.py             ← ProductMaterialBase +3 campos
  mt-pricing-backend/app/schemas/products.py               ← ProductResponse.model_id + ProductDetail.model_detail
  mt-pricing-backend/app/repositories/product.py           ← selectinload(Product.model)
  mt-pricing-backend/app/api/routes/products.py            ← _build_product_detail + 2 endpoints

BACKEND — crear:
  mt-pricing-backend/app/schemas/product_models.py         ← ProductModelResponse + CertificateResponse + ModelFlowDataResponse

FRONTEND — modificar:
  mt-pricing-frontend/lib/api/endpoints/products.ts        ← interfaces ProductModelDetail + CertificateItem + ModelFlowDataItem + Product.model_detail
  mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx  ← KVPs modelo
  mt-pricing-frontend/app/(app)/catalogo/[sku]/page.tsx    ← secciones certificados + flow data

FRONTEND — crear:
  mt-pricing-frontend/lib/hooks/products/use-product-model.ts    ← useProductCertificates + useProductFlowData
  mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx
  mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx
```

---

## Task 1: Backend — Schemas nuevos (product_models.py)

**Files:**
- Create: `mt-pricing-backend/app/schemas/product_models.py`

- [ ] **Crear el archivo con los tres schemas**

```python
# mt-pricing-backend/app/schemas/product_models.py
"""Pydantic v2 schemas para la jerarquía product_models (mig 126-127)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    series_id: UUID | None = None
    code: str
    color_label: str | None = None
    connection_type: str | None = None
    thread_standard: str | None = None
    active: bool
    variant_of_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    model_id: UUID | None = None
    cert_number: str
    issuer: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    status: str
    signatory_name: str | None = None
    signatory_role: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ModelFlowDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    model_id: UUID
    dn_mm: int
    kv: float | None = None
    cv: float | None = None
    mesh_mm: float | None = None
```

- [ ] **Verificar que el módulo importa sin errores**

```bash
cd mt-pricing-backend
python -c "from app.schemas.product_models import ProductModelResponse, CertificateResponse, ModelFlowDataResponse; print('OK')"
```

Expected: `OK`

- [ ] **Commit**

```bash
git add mt-pricing-backend/app/schemas/product_models.py
git commit -m "feat(schemas): ProductModelResponse + CertificateResponse + ModelFlowDataResponse"
```

---

## Task 2: Backend — Extender SeriesResponse + ProductMaterialBase

**Files:**
- Modify: `mt-pricing-backend/app/schemas/vocabularies.py` (SeriesResponse ~línea 586)
- Modify: `mt-pricing-backend/app/schemas/components.py` (ProductMaterialBase ~línea 48)

- [ ] **Añadir campos a SeriesResponse**

En `vocabularies.py`, después de `updated_at: datetime` en `SeriesResponse` (actualmente el último campo antes del cierre de clase), añadir:

```python
    # mig 128 — nuevos campos de serie
    thread_standard: str | None = None
    revision: str | None = None
    revision_date: "date | None" = None
```

Y añadir el import de `date` al top del archivo si no existe:
```python
from datetime import date, datetime
```

- [ ] **Añadir campos de grado a ProductMaterialBase**

En `components.py`, en `ProductMaterialBase`, después de `observations`:

```python
    material_grade: str | None = Field(default=None, max_length=128)
    material_standard: str | None = Field(default=None, max_length=64)
    surface_treatment: str | None = Field(default=None, max_length=128)
```

Y en `ProductMaterialPatch`, añadir los mismos tres campos opcionales:

```python
    material_grade: str | None = Field(default=None, max_length=128)
    material_standard: str | None = Field(default=None, max_length=64)
    surface_treatment: str | None = Field(default=None, max_length=128)
```

- [ ] **Verificar imports**

```bash
cd mt-pricing-backend
python -c "from app.schemas.vocabularies import SeriesResponse; from app.schemas.components import ProductMaterialResponse; print('OK')"
```

Expected: `OK`

- [ ] **Commit**

```bash
git add mt-pricing-backend/app/schemas/vocabularies.py mt-pricing-backend/app/schemas/components.py
git commit -m "feat(schemas): series thread_standard/revision + material grade fields (mig 128-129)"
```

---

## Task 3: Backend — Extender ProductResponse + ProductDetail

**Files:**
- Modify: `mt-pricing-backend/app/schemas/products.py`

- [ ] **Añadir import de ProductModelResponse**

Al bloque de imports en la parte superior de `products.py`, añadir:

```python
from app.schemas.product_models import ProductModelResponse
```

- [ ] **Añadir model_id a ProductResponse**

En `ProductResponse` (clase, después de `division_codes`):

```python
    model_id: UUID | None = None
```

- [ ] **Añadir model_detail a ProductDetail**

En `ProductDetail` (después de `display_pair`):

```python
    model_detail: ProductModelResponse | None = None
```

- [ ] **Verificar imports**

```bash
cd mt-pricing-backend
python -c "from app.schemas.products import ProductResponse, ProductDetail; p = ProductDetail.model_fields; print('model_id' in p, 'model_detail' in p)"
```

Expected: `True True`

- [ ] **Commit**

```bash
git add mt-pricing-backend/app/schemas/products.py
git commit -m "feat(schemas): ProductResponse.model_id + ProductDetail.model_detail"
```

---

## Task 4: Backend — Repositorio: cargar relación model

**Files:**
- Modify: `mt-pricing-backend/app/repositories/product.py` (~línea 57-66)

- [ ] **Añadir selectinload en get_by_sku**

En el método `get_by_sku` (el bloque `.options(...)` que tiene `selectinload(Product.translations)`), añadir al final del bloque options:

```python
                selectinload(Product.model),
```

El bloque completo quedará:

```python
        stmt = (
            select(Product)
            .where(Product.sku == sku)
            .options(
                selectinload(Product.translations),
                selectinload(Product.assets),
                selectinload(Product.product_divisions).selectinload(
                    ProductDivision.division
                ),
                selectinload(Product.model),
            )
        )
```

- [ ] **Verificar que Product.model existe como relationship**

```bash
cd mt-pricing-backend
python -c "from app.db.models.product import Product; print(hasattr(Product, 'model'))"
```

Expected: `True`

- [ ] **Commit**

```bash
git add mt-pricing-backend/app/repositories/product.py
git commit -m "feat(repo): selectinload(Product.model) en get_by_sku"
```

---

## Task 5: Backend — _build_product_detail + nuevos endpoints

**Files:**
- Modify: `mt-pricing-backend/app/api/routes/products.py`

### Paso 5a: Extender _build_product_detail

- [ ] **Añadir import de ProductModelResponse al bloque de imports del routes**

En los imports del top del archivo `products.py`, añadir junto a los demás imports de schemas:

```python
from app.schemas.product_models import (
    CertificateResponse,
    ModelFlowDataResponse,
    ProductModelResponse,
)
```

- [ ] **Añadir model_detail a _build_product_detail**

En la función `_build_product_detail` (~línea 230), en el dict `detail_data`, añadir `"model_detail": None` junto a los otros:

```python
    detail_data: dict[str, Any] = {
        **base,
        "translations": [...],
        "images": [...],
        "primary_image_url": primary_image_url,
        "series_detail": None,
        "material_detail": None,
        "display_pair": None,
        "model_detail": None,     # ← añadir
    }
```

Después del bloque que carga `material_detail`, añadir:

```python
    if prod.model is not None:
        detail_data["model_detail"] = ProductModelResponse.model_validate(prod.model)
```

### Paso 5b: Endpoint GET /products/{sku}/certificates

- [ ] **Añadir el endpoint después del handler de `get_product` (~línea 713)**

```python
@router.get(
    "/{sku}/certificates",
    response_model=list[CertificateResponse],
    summary="Certificados del modelo al que pertenece el SKU",
)
async def get_product_certificates(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CertificateResponse]:
    from sqlalchemy import select as _select
    from app.db.models.certificates import Certificate
    from app.db.models.product import Product as _Prod

    result = await session.execute(
        _select(_Prod.model_id).where(_Prod.sku == sku)
    )
    model_id = result.scalar_one_or_none()
    if not model_id:
        return []
    certs = (
        await session.execute(
            _select(Certificate)
            .where(Certificate.model_id == model_id)
            .order_by(Certificate.expires_at.nulls_last(), Certificate.cert_number)
        )
    ).scalars().all()
    return [CertificateResponse.model_validate(c) for c in certs]
```

### Paso 5c: Endpoint GET /products/{sku}/flow-data

- [ ] **Añadir el endpoint a continuación**

```python
@router.get(
    "/{sku}/flow-data",
    response_model=list[ModelFlowDataResponse],
    summary="Coeficientes de flujo Kv/Cv del modelo del SKU (filtros/coladores)",
)
async def get_product_flow_data(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    _: Annotated[User, Depends(require_permissions("products:read"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ModelFlowDataResponse]:
    from sqlalchemy import select as _select
    from app.db.models.product_models import ModelFlowData
    from app.db.models.product import Product as _Prod

    result = await session.execute(
        _select(_Prod.model_id).where(_Prod.sku == sku)
    )
    model_id = result.scalar_one_or_none()
    if not model_id:
        return []
    rows = (
        await session.execute(
            _select(ModelFlowData)
            .where(ModelFlowData.model_id == model_id)
            .order_by(ModelFlowData.dn_mm)
        )
    ).scalars().all()
    return [ModelFlowDataResponse.model_validate(r) for r in rows]
```

- [ ] **Verificar que el módulo importa sin errores**

```bash
cd mt-pricing-backend
python -c "from app.api.routes.products import router; print('OK')"
```

Expected: `OK`

- [ ] **Redesplegar backend y smoke test**

```bash
docker restart mt-backend
sleep 3
# Verificar health
curl http://localhost:8081/health/live
# Verificar que los nuevos paths aparecen en OpenAPI
curl -s http://localhost:8081/api/v1/openapi.json | python -c "import json,sys; d=json.load(sys.stdin); paths=[p for p in d['paths'] if 'certificates' in p or 'flow-data' in p]; print(paths)"
```

Expected: `['/api/v1/products/{sku}/certificates', '/api/v1/products/{sku}/flow-data']`

- [ ] **Commit**

```bash
git add mt-pricing-backend/app/api/routes/products.py
git commit -m "feat(api): GET /products/{sku}/certificates + /flow-data + model_detail en ProductDetail"
```

---

## Task 6: Frontend — TypeScript types

**Files:**
- Modify: `mt-pricing-frontend/lib/api/endpoints/products.ts`

- [ ] **Añadir interfaces nuevas (antes de `export const productsApi`)**

```typescript
export interface ProductModelDetail {
  id: string;
  series_id: string | null;
  code: string;
  color_label: string | null;
  connection_type: string | null;
  thread_standard: string | null;
  active: boolean;
  variant_of_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CertificateItem {
  id: string;
  model_id: string | null;
  cert_number: string;
  issuer: string | null;
  issued_at: string | null;   // ISO date "YYYY-MM-DD"
  expires_at: string | null;  // ISO date "YYYY-MM-DD"
  status: "valid" | "expiring_soon" | "critical" | "expired" | "renewing";
  signatory_name: string | null;
  signatory_role: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ModelFlowDataItem {
  id: string;
  model_id: string;
  dn_mm: number;
  kv: number | null;
  cv: number | null;
  mesh_mm: number | null;
}
```

- [ ] **Extender ProductSeriesDetail con campos mig 128**

```typescript
export interface ProductSeriesDetail {
  id: string;
  code: string;
  name_en: string;
  tier_id?: string | null;
  thread_standard?: string | null;   // mig 128
  revision?: string | null;          // mig 128
  revision_date?: string | null;     // mig 128
}
```

- [ ] **Añadir model_id y model_detail a Product**

En `interface Product extends ProductListItem`, añadir junto a los demás campos opcionales:

```typescript
  model_id?: string | null;
  model_detail?: ProductModelDetail | null;
```

- [ ] **Añadir métodos a productsApi**

Al final de `productsApi` (antes del cierre `}`):

```typescript
  getCertificates: (sku: string): Promise<CertificateItem[]> =>
    authedFetch<CertificateItem[]>(`/api/v1/products/${sku}/certificates`),

  getFlowData: (sku: string): Promise<ModelFlowDataItem[]> =>
    authedFetch<ModelFlowDataItem[]>(`/api/v1/products/${sku}/flow-data`),
```

- [ ] **Verificar TypeScript**

```bash
cd mt-pricing-frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: 0 errores relacionados con los tipos nuevos.

- [ ] **Commit**

```bash
git add mt-pricing-frontend/lib/api/endpoints/products.ts
git commit -m "feat(fe/types): ProductModelDetail + CertificateItem + ModelFlowDataItem + Product.model_detail"
```

---

## Task 7: Frontend — Hooks para model certificates + flow-data

**Files:**
- Create: `mt-pricing-frontend/lib/hooks/products/use-product-model.ts`

- [ ] **Crear el archivo de hooks**

```typescript
// mt-pricing-frontend/lib/hooks/products/use-product-model.ts
import { useQuery } from "@tanstack/react-query";
import { productsApi } from "@/lib/api/endpoints/products";

export function useProductCertificates(sku: string) {
  return useQuery({
    queryKey: ["products", sku, "certificates"],
    queryFn: () => productsApi.getCertificates(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}

export function useProductFlowData(sku: string) {
  return useQuery({
    queryKey: ["products", sku, "flow-data"],
    queryFn: () => productsApi.getFlowData(sku),
    enabled: !!sku,
    staleTime: 120_000,
  });
}
```

- [ ] **Commit**

```bash
git add mt-pricing-frontend/lib/hooks/products/use-product-model.ts
git commit -m "feat(fe/hooks): useProductCertificates + useProductFlowData"
```

---

## Task 8: Frontend — Componente product-certificates.tsx

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx`

- [ ] **Crear el componente**

```tsx
// mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx
"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProductCertificates } from "@/lib/hooks/products/use-product-model";
import type { CertificateItem } from "@/lib/api/endpoints/products";

const STATUS_CLASSES: Record<string, string> = {
  valid: "border-green-300 bg-green-50 text-green-700",
  expiring_soon: "border-yellow-300 bg-yellow-50 text-yellow-700",
  critical: "border-orange-300 bg-orange-50 text-orange-700",
  expired: "border-red-300 bg-red-50 text-red-700",
  renewing: "border-blue-300 bg-blue-50 text-blue-700",
};

function StatusBadge({ status }: { status: CertificateItem["status"] }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${STATUS_CLASSES[status] ?? ""}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", {
    year: "numeric",
    month: "short",
  });
}

export function ProductCertificates({ sku }: { sku: string }) {
  const { data: certs, isLoading } = useProductCertificates(sku);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!certs?.length) return null;

  return (
    <section aria-label="Certificados" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Certificados
      </h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium">Número</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Emisor</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Emisión</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Vencimiento</th>
              <th className="px-3 py-2 text-left text-xs font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {certs.map((c) => (
              <tr key={c.id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{c.cert_number}</td>
                <td className="px-3 py-2 text-xs">{c.issuer ?? "—"}</td>
                <td className="px-3 py-2 text-xs">{fmtDate(c.issued_at)}</td>
                <td className="px-3 py-2 text-xs">{fmtDate(c.expires_at)}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={c.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-certificates.tsx"
git commit -m "feat(fe): ProductCertificates component"
```

---

## Task 9: Frontend — Componente product-flow-data.tsx

**Files:**
- Create: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx`

- [ ] **Crear el componente**

```tsx
// mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx
"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useProductFlowData } from "@/lib/hooks/products/use-product-model";

export function ProductFlowData({ sku }: { sku: string }) {
  const { data: rows, isLoading } = useProductFlowData(sku);

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!rows?.length) return null;

  return (
    <section aria-label="Coeficientes de flujo" className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Coeficientes de flujo
      </h2>
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium">DN (mm)</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Kv (m³/h)</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Cv</th>
              <th className="px-3 py-2 text-right text-xs font-medium">Malla (mm)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{r.dn_mm}</td>
                <td className="px-3 py-2 text-right text-xs">{r.kv ?? "—"}</td>
                <td className="px-3 py-2 text-right text-xs">{r.cv ?? "—"}</td>
                <td className="px-3 py-2 text-right text-xs">{r.mesh_mm ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
```

- [ ] **Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-flow-data.tsx"
git commit -m "feat(fe): ProductFlowData component"
```

---

## Task 10: Frontend — product-header.tsx: KVPs de modelo

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx`

- [ ] **Añadir import de Badge si no existe**

En los imports, verificar que `Badge` está importado desde `@/components/ui/badge` (ya existe en línea 9).

- [ ] **Añadir KVPs de modelo en la dl de Quick Facts**

En el bloque de vista normal (no editMode), después de `<KVP label="Serie" value={seriesLabel} />`:

```tsx
          {product.model_detail ? (
            <>
              <KVP
                label="Modelo"
                value={
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono">{product.model_detail.code}</span>
                    {product.model_detail.color_label ? (
                      <Badge variant="outline" className="text-[10px] capitalize">
                        {product.model_detail.color_label}
                      </Badge>
                    ) : null}
                  </span>
                }
              />
              {product.model_detail.connection_type ? (
                <KVP
                  label="Conexión"
                  value={product.model_detail.connection_type}
                />
              ) : null}
            </>
          ) : null}
```

- [ ] **Redesplegar frontend y verificar**

```bash
docker restart mt-frontend
```

Navegar a `/catalogo/4097015` (logueado) y verificar que aparecen los KVPs de Modelo y Conexión cuando el SKU tiene `model_detail`.

- [ ] **Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/_components/product-header.tsx"
git commit -m "feat(fe): product-header KVPs modelo + conexión desde model_detail"
```

---

## Task 11: Frontend — spec page: certificados + flow data

**Files:**
- Modify: `mt-pricing-frontend/app/(app)/catalogo/[sku]/page.tsx`

- [ ] **Añadir imports**

```tsx
import { ProductCertificates } from "./_components/product-certificates";
import { ProductFlowData } from "./_components/product-flow-data";
```

- [ ] **Añadir secciones al final del JSX (antes del cierre del div)**

```tsx
      <ProductFlowData sku={sku} />
      <ProductCertificates sku={sku} />
```

Las secciones usan `isLoading` y `data?.length` internamente — si no hay datos no renderizan nada, así que no hay riesgo de layout shift cuando el modelo no tiene estos datos.

- [ ] **Redesplegar frontend**

```bash
docker restart mt-frontend
```

- [ ] **Verificar en browser** — navegar a `/catalogo/4097015` → tab de specs. Si el modelo del SKU tiene certificados o flow data, aparecen al final de la página. Si no tiene, la página se ve igual que antes (sin secciones vacías).

- [ ] **Commit**

```bash
git add "mt-pricing-frontend/app/(app)/catalogo/[sku]/page.tsx"
git commit -m "feat(fe/catalog): secciones certificados + coeficientes de flujo en spec page"
```

---

## Self-review checklist

- [x] **Spec coverage**: Todos los 9 gaps del diagnóstico están cubiertos (Tasks 1-11)
- [x] **Placeholders**: No hay TBD ni TODO — todo el código está completo
- [x] **Type consistency**: `CertificateItem` / `ModelFlowDataItem` usados consistentemente en types, hooks, y componentes
- [x] **ProductModelResponse** importado en `products.py` routes y en `ProductDetail`
- [x] **selectinload(Product.model)** en el mismo método que los demás eager loads
- [x] **Endpoints usan `Annotated[...]` + `Depends`** consistente con el resto del router
- [x] **Components retornan null cuando no hay datos** — no hay secciones vacías en la UI
