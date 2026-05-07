# ADR-016: Arquitectura Hexagonal para connectors de canal

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

Fase 1 sólo entrega connector base + filtro por estado aprobado. Fases 3+ traen connectors reales: Amazon UAE FBA/FBM, Noon UAE, Shopify (storefront), B2B portal, futuros marketplaces GCC.

Cada marketplace tiene API distinta (Amazon SP-API, Noon Seller API, Shopify Admin REST/GraphQL, ...). La lógica de pricing + workflow + audit no debe acoplarse a ninguna API específica.

## Decisión

**Hexagonal Architecture (Ports & Adapters)** para connectors.

### Puerto

```typescript
// src/domain/channel/ports/ChannelPublisher.ts

export interface ChannelPublisher {
  readonly channelCode: string;

  /** Validate that records are publishable to this channel; does NOT call external API. */
  validate(records: PublishableRecord[]): ValidationResult;

  /** Push validated records to the external channel. Returns per-record outcome. */
  publish(records: PublishableRecord[]): Promise<PublishOutcome>;

  /** Pull current state from external channel for reconciliation. Optional. */
  reconcile?(): Promise<ReconcileReport>;
}
```

### Tipos

```typescript
type PublishableRecord = {
  sku: string;
  scheme: SchemeCode;
  price: PriceSnapshot;        // estado approved | auto_approved
  product: ProductSnapshot;
  translations: TranslationsSnapshot;
  images: ImageRefs;
};

type PublishOutcome = {
  published: PublishedRecord[];
  rejected: RejectedRecord[];   // con razón
  externalIds: Map<string, string>; // sku → ASIN/NIN/...
};
```

### Implementación base

`BaseChannelPublisher` (clase abstract) implementa:
- Filtro por estado aprobado (regla dura ADR-010).
- Filtro por estado canal (`pilot`/`live` solamente).
- Audit emit antes/después de publish.
- Retry policy con backoff exponencial.
- Métricas (`publish_total`, `publish_failed_total`, `publish_latency_ms`).
- Idempotency (record key = `sku|channel|scheme|price_id`).

Adapters heredan y sólo implementan transport HTTP/SDK específico:
- `AmazonUaeFbaPublisher extends BaseChannelPublisher` — implementa Amazon SP-API.
- `AmazonUaeFbmPublisher extends BaseChannelPublisher`.
- `NoonUaePublisher extends BaseChannelPublisher`.
- `ShopifyPublisher extends BaseChannelPublisher`.
- `MockPublisher extends BaseChannelPublisher` — para tests + Fase 1 (no marketplace real, sólo dry run / shadow publish).

### Fase 1 entrega

- Sólo `BaseChannelPublisher` + `MockPublisher` (= shadow publish a archivo / S3 que TI puede inspeccionar).
- Tests e2e validan que `MockPublisher` rechaza precios no aprobados.
- Adapters reales son Fase 3.

### Configuración por adapter

- Tabla `channel_credentials` (cifrada con `pgcrypto`):
  ```sql
  CREATE TABLE channel_credentials (
    channel_code TEXT PRIMARY KEY REFERENCES channels(code),
    credentials_encrypted BYTEA NOT NULL,
    rotated_at TIMESTAMPTZ,
    rotated_by UUID
  );
  ```
- Solo `ti_integracion` y `admin` pueden configurar.
- Cargado en memoria con cache TTL al iniciar el worker; rotación periódica.

### Modelo de datos de tracking

```sql
CREATE TABLE price_exports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  price_id UUID NOT NULL REFERENCES prices(id),
  channel_code TEXT NOT NULL REFERENCES channels(code),
  external_id TEXT,         -- ASIN, NIN
  status TEXT NOT NULL,     -- 'queued'|'in_flight'|'success'|'failed'
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ,
  attempts INT DEFAULT 0,
  last_error TEXT
);
```

## Alternativas evaluadas

### Alternativa A: Code monolítico — un service por connector con su propia copy de la lógica
- **Pros**: simplicidad inicial.
- **Contras**: cada nuevo connector duplica lógica de filtro / audit / retry. Bug en uno no se fix en otros automáticamente.
- **Veredicto**: descartada.

### Alternativa B: Workflow externo (Make.com / n8n / Zapier)
- **Pros**: visual, no-code-friendly.
- **Contras**: stack rechazado en brief. Lock-in. No control de regla dura ADR-010 (workflow visual puede tener escapatorias).
- **Veredicto**: descartada.

### Alternativa C: iPaaS dedicado (MuleSoft, Boomi)
- **Pros**: maduro.
- **Contras**: enterprise pricing. Overkill.
- **Veredicto**: descartada.

## Consecuencias positivas

- Añadir un canal nuevo = sólo crear un adapter (transport).
- Reglas de negocio (filtro de estado, audit, retry) consistentes entre canales.
- Tests del puerto son tests del comportamiento, no del marketplace real.
- Mock publisher Fase 1 valida flujo end-to-end sin marketplace real.

## Consecuencias negativas / riesgos

- Abstracción tiene coste cognitivo. Mitigación: documentación + ejemplo MockPublisher de referencia.
- Si dos canales son muy distintos (REST vs GraphQL vs SOAP), el puerto puede quedar lowest common denominator. Mitigación: extender el puerto con métodos opcionales y caps `supports: {bulk_publish, partial_update, ...}`.

## Cuándo revisar

- **Fase 3** (primer adapter real): validar que el puerto sostiene Amazon SP-API.
- **Cuando se añada el segundo adapter**: re-evaluar abstractions; refactor si el puerto fue diseñado prematuro.
