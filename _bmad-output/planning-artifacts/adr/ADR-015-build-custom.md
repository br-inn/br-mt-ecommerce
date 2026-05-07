# ADR-015: Build custom (alternativas Akeneo / Pimcore / Odoo descartadas)

- Status: accepted (preservada de la decisión adoptada en brief)
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador)

## Contexto

Antes de comprometer build custom para Fase 1, se evaluaron suites maduras del mercado para PIM, ERP, pricing y combinaciones.

## Decisión

**Build custom**. Documentar formalmente la decisión Build vs Buy.

## Alternativas evaluadas

### Alternativa A: Akeneo / Pimcore (PIM open-source)
- **Pros**: PIM maduro, multi-idioma de fábrica, comunidad.
- **Contras**:
  - El motor de pricing multi-canal/multi-esquema **queda fuera** de sus capacidades core. Habría que extender PHP / Symfony.
  - El workflow de aprobación por excepción no es nativo; los workflows de Akeneo son simples (aprobación lineal, no por reglas paramétricas).
  - Integración con el comparador de productos (research workstream) requiere reescribir capa de scoring + integration heavy.
  - UI heavy/lenta para uso ágil de equipo de 3.
  - Coste total = licensing (Akeneo PIM Enterprise) + customización + integración + hosting > build custom para 224 SKUs.
- **Veredicto**: descartada.

### Alternativa B: Odoo (ERP + PIM + e-commerce)
- **Pros**: suite integrada, multi-módulo, multi-idioma, multi-divisa.
- **Contras**:
  - Pricing por canal/esquema requiere customización profunda (Odoo `pricelist` modela canal como tarifa pero no soporta workflow por excepción ni FX as-of de la forma requerida).
  - Lock-in al stack Python/PostgreSQL de Odoo + framework propio (record sets, ORM proprietary).
  - Customización + actualización futura es compleja (cualquier upgrade de Odoo puede romper customs).
  - Equipo de 3 + 224 SKUs es underutilization de Odoo (típico para 50-500 empleados).
- **Veredicto**: descartada.

### Alternativa C: NetSuite
- **Pros**: enterprise-grade.
- **Contras**: coste licensing $$$$/mes, implementación 6-12 meses, partner consultoría obligatorio. Para mid-market UAE inviable.
- **Veredicto**: descartada.

### Alternativa D: SAP Business One
- **Pros**: ecosistema SAP.
- **Contras**: pesado para 224 SKUs, customización vía SDK/UI propietario, partners locales caros, lock-in.
- **Veredicto**: descartada.

### Alternativa E: Pricefx / Vendavo (enterprise pricing)
- **Pros**: pricing optimization madura.
- **Contras**: enterprise pricing tools — coste US$ 50k-200k/año, implementación meses. PIM no incluido. Para mid-market UAE con 224 SKUs es absurdo.
- **Veredicto**: descartada.

### Alternativa F: Combinación (Akeneo PIM + Pricefx + custom integration)
- **Pros**: best of breed.
- **Contras**: tres vendors → tres contratos, tres data syncs, tres equipos de soporte. Costo total >> build custom + complejidad de integración.
- **Veredicto**: descartada.

### Alternativa G: Build custom (Next.js + Postgres)
- **Pros**:
  - Control total del modelo de datos.
  - Motor de pricing v5.1 codificado como diferencial específico MT.
  - Integración nativa con research workstream del comparador.
  - Reuso transparente para Fases 2-4 (inventario, B2C/marketplaces, B2B) sin licencias incrementales.
  - Multi-tenant explícitamente NO necesario (single-tenant — ADR-014).
  - Plataforma propiedad MT/BR, no licencia externa.
  - Coste a escala: $0 incremental por usuario, sólo infra.
- **Contras**:
  - Equipo BR debe construir y mantener.
  - Tiempo de bootstrap: ~14 semanas Fase 1.
  - Riesgo de re-inventar pieces estandar (importer, audit, RBAC) — mitigado con stack moderno (Prisma, Auth.js, Zod).
- **Veredicto**: **adoptada**.

## Consecuencias positivas

- Diferenciación: la plataforma encapsula 18+ meses de reglas v5.1 + research del comparador. Eso no se compra.
- Coste predecible: salario BR + infra (~$200-500/mes Fase 1).
- Velocidad de cambio: cualquier ajuste se hace por código, no por configuración limitada.
- Roadmap controlado: Fases 2-4 montan encima sin tocar el núcleo.

## Consecuencias negativas / riesgos

- BR es bus factor — si BR Innovation no continúa, MT necesita capacidad de mantenimiento. Mitigación: documentación denso + handoff TI MT (ya en el plan); plataforma en stack mainstream (TS/Postgres) reclutable.
- Construir importer + audit + RBAC desde cero tiene esfuerzo ya tarifado en Fases 1a/1b.
- Sin "garantías de proveedor" externas (vs SAP/Odoo). Mitigación: SLA y soporte BR contractual.

## Cuándo revisar

- **Cierre Fase 1b**: ¿la plataforma cumple su promesa? Si sí, se confirma Build. Si no, replantear (no se ha hecho ningún sunk-cost que impida revisar).
- **Antes de Fase 2** (inventarios + facturación e-invoicing UAE): re-evaluar si vale la pena módulos COTS específicos (e-invoicing UAE certificado puede ser SaaS especializado, no build).
- **Si MT crece a 50k SKUs y 50 usuarios**: re-evaluar capacidad operativa de la plataforma.
