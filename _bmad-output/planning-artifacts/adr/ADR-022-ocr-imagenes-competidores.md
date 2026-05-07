# ADR-022: OCR sobre imágenes de competidores

- Status: proposed
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT
- Related: ADR-012, ADR-013, ADR-024, FR-CMP-OCR-01

## Contexto

En válvulas, fittings y conexiones (PVF), información crítica para el matching está **físicamente grabada o impresa sobre el cuerpo** del producto: marca, número de parte, DN, PN, material, clase de presión, certificaciones (`WRAS`, `ACS`). Una proporción alta de los listings de Amazon UAE / Noon UAE / fabricantes muestra ese texto legible.

El stack original del spike (v1.0) consideraba sólo embeddings de imagen + texto del título + specs JSONB. No aprovechaba el texto grabado / impreso de la imagen, perdiendo una **dimensión de matching de altísimo valor** (marca real + part-number exacto), especialmente útil cuando el título del listing es genérico o engañoso.

La recomendación externa al sponsor (2026-05-06) propone añadir OCR como capa pre-scoring, posicionada entre el normalizador de candidatos y el scorer multi-dimensional, ejecutada en paralelo al embedder de imagen.

## Decisión

Añadir OCR como capa obligatoria del pipeline:

- **Proveedor por defecto Fase 1**: **Google Vision OCR** (`DOCUMENT_TEXT_DETECTION`).
- **Justificación**: mejor accuracy en grabados pequeños, superficies curvas y metal reflectante; soporte 50+ idiomas con cobertura nativa de árabe; orientación auto; latencia 0,3-1 s; coste ~$1,50 / 1 000 imágenes.
- **Abstracción**: puerto `OcrService` (TypeScript) con adapter por proveedor; permite cambio sin tocar el scorer.
- **Adapter de fallback Fase 1**: `TesseractOcrAdapter` self-host, para escenario donde TI MT exija no enviar imágenes a Google Cloud (residencia de datos UAE).
- **Volumen optimizado**: el OCR se ejecuta sólo sobre **el top-10 de candidatos shortlistados por embedding de imagen**, no sobre todo el universo de candidatos. Reduce volumen ~5×.
- **Persistencia**: tabla nueva `competitor_listing_ocr` (ver arquitectura §17.9) con `ocr_text`, `ocr_blocks` (bounding boxes + confidence), `ocr_languages`, metadata de proveedor y coste por llamada.
- **Consumo en scorer**: dimensión `score_ocr` con peso 0,15 cuando el OCR contenga (a) la marca esperada del SKU, (b) un patrón de part-number consistente con la marca, o (c) DN/PN coincidentes.

## Alternativas evaluadas

- **Tesseract OCR self-host como default**: gratis (sólo compute), pero accuracy baja en grabados pequeños / metal reflectante / texto rotado. Sí queda como adapter de fallback.
- **AWS Textract**: bueno para documentos (formularios, tablas) pero peor en fotos de producto; soporte AR limitado.
- **Azure Computer Vision OCR**: calidad similar a Google Vision; descartado por mantener stack neutral (no Azure obligado).
- **Mistral OCR / Claude vision como OCR LLM-based**: 5-10× más caro; valor añadido (reasoning + OCR juntos) ya cubierto por el VLM judge en cascada (ADR-024). Descartado por coste.
- **No OCR (status quo v1.0 del spike)**: pierde una dimensión de matching alta, especialmente para SKUs sin specs estructuradas en el listing. Descartado.

## Consecuencias positivas

- +5-10 puntos de F1 esperados en matching cuando la imagen es legible (hipótesis a validar en POC).
- Confirmación de marca real (anti-counterfeit signal) cuando título dice "Pegler" pero el cuerpo dice marca genérica.
- Reduce llamadas al VLM judge (más caro) porque el OCR resuelve casos antes.
- Accuracy en árabe nativa habilita mercado AR sin trabajo adicional.

## Consecuencias negativas / riesgos

- Coste incremental: ~$150/mes a 100k OCRs / mes (asumible y proporcional al stack ~$240-340/mes).
- Dependencia de Google Cloud (mitigado por adapter Tesseract).
- Falsos positivos cuando el OCR lee texto del fondo (etiquetas de packaging) en vez del cuerpo del producto. Mitigación: bounding boxes + heurística de área central + confidence threshold > 0,7.
- Latencia adicional 0,3-1 s por imagen (paraleliza fácil con embedding de imagen).
- Residencia de datos: enviar imágenes a Google Cloud (.com) puede chocar con políticas TI MT. Mitigación: switch a Tesseract por config.

## Cuándo revisar

- **S2**: tras 100 imágenes OCR'd y etiquetadas, validar mejora F1 vs baseline sin OCR. Si < +3 F1, reconsiderar peso 0,15 → 0,10.
- **G2 (S2-S3)**: revalidar coste real vs proyectado.
- **G4 (S6)**: si se decide diferir comparador a Fase 1.5, OCR queda no activado pero hooks listos.
