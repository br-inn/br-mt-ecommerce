# ADR-025: Capa humana de validación como infraestructura permanente

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), Comercial Online MT, Gerente Comercial
- Related: ADR-012, ADR-024, FR-CMP-JUDGE-01

## Contexto

El framing original del spike v1.0 implícitamente trataba la cola de validación humana como una **medida transitoria**: "mientras el calibrator madura, el humano cubre la zona gris; cuando madure, automatizamos más y achicamos la cola". Esa lectura llevaba a optimizar para "% de pares auto-resueltos sin humano" como KPI, lo que distorsiona incentivos (subir threshold de auto-match indefinidamente, aceptando peor precisión).

La recomendación externa al sponsor (2026-05-06) introduce un reframing fuerte:

> *"Los líderes en este espacio (Centric Software, Intelligence Node, DataWeave) usan revisión humana como parte permanente del proceso. Es lo que separa el 92 % del 99 %."*

Implicación: la capa humana **no es un placeholder de Fase 1.5+**. Es **infraestructura permanente** del subsistema de comparación, a perpetuidad, alineada con cómo operan los líderes del segmento. La inversión a futuro va en optimizar productividad por validador, no en eliminar la cola.

## Decisión

1. **La cola de validación humana es componente productivo permanente** del subsistema de comparación, no transitorio.
2. **KPIs del subsistema cambian**:
   - **NO** se mide "% de pares auto-resueltos sin humano" como objetivo a maximizar.
   - **SÍ** se mide:
     - Precisión global ≥ 99 % (combinando auto + human).
     - Productividad por validador (≥ 250 pares/h sostenido, ≥ 360 pares/h pico).
     - Tiempo medio de validación (≤ 24 h SLA).
     - Lift de productividad por mejora de UI (active learning order, atajos teclado, mostrar judge_rationale antes del score, mostrar OCR extraído como contexto).
3. **Threshold de auto-match no se sube indefinidamente**. Se mantiene en una zona donde el coste de error excede el coste humano.
4. **Plan de personal**:
   - Fase 1: 1 validador freelance UAE, 10 h/sem, $15/h → ~$600/mes.
   - Fase 2 (50k SKUs): 2-3 validadores escalonados.
   - Fase 3+: equipo dedicado con escalación a Comercial / Gerente para casos complejos.
5. **Contrato de §17.2-17.3 de la arquitectura se modifica**: aún si el research entrega Fase 1, la cola humana **NO se desactiva** ni se trata como degradado.

## Alternativas evaluadas

- **Tratar la cola como transitoria, objetivo eliminarla con más automatización (status quo v1.0)**: distorsiona KPIs, fuerza thresholds altos que sacrifican precisión, repite el patrón fallido del v5.1 (15 % sin match no aceptable). Descartado.
- **Outsourcing total (Mechanical Turk / Scale AI)**: scale lo permite, pero pierdes control de sesgo dominio + auditabilidad VAT. Reservado para tareas no críticas Fase 4+.
- **Validador full-time interno MT**: a 224 SKUs no amortiza; carga insuficiente. A 50k SKUs sí; documentado como upgrade Fase 2.

## Consecuencias positivas

- Precisión global más alta y sostenible (target 99 %).
- Auditabilidad real: cada decisión final tiene firma humana + rationale del VLM.
- Defendible ante auditoría VAT UAE 2026 (humano siempre puede explicar por qué).
- Alineado con líderes del mercado.

## Consecuencias negativas / riesgos

- Coste recurrente de personal: ~$600/mes Fase 1, escala con catálogo.
- Dependencia de capacidad humana: si la validadora freelance se ausenta sin backup, la cola crece. Mitigación: pool de 2 freelancers + Champion del cambio como backup.
- Riesgo de fatiga / sesgo: rotación obligatoria + consenso de 2 validadores en pares críticos.
- Stakeholder management: Gerente puede pedir "más automatización" como meta. Mitigación: este ADR es la respuesta documentada.

## Cuándo revisar

- **S5**: medir productividad real (pares/h) y ajustar capacidad.
- **G4 (S6)**: ratificar plan de personal Fase 1 → Fase 2.
- Cuando catálogo crezca > 10k SKUs: evaluar añadir 2.º validador.
- Si Centric / Intelligence Node demuestran 99 % sin capa humana en demo: re-evaluar (pero verificar si no esconden capa humana propia detrás).
