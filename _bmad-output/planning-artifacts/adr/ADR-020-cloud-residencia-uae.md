# ADR-020: Cloud y residencia de datos UAE

- Status: open / pending S0
- Date: 2026-05-06
- Deciders: Pablo Sierra (BR), Christian (MT sponsor), Paula (MT validador), TI MT

## Contexto

VAT UAE 2026 + e-invoicing + posibilidad de regulación de data localization GCC abren la pregunta: **¿los datos del catálogo + precios + audit deben residir en UAE?**

A día de hoy, **no hay obligación legal explícita** de data residency UAE para este tipo de datos B2B/B2C de productos + precios. Pero:
- Ley federal UAE No. 45/2021 (Personal Data Protection Law) aplica a datos personales — sólo afecta a `users` table (3-10 personas internas), gestionable.
- Regulaciones FTA + e-invoicing piden auditabilidad + access; la residencia técnica es secundaria.
- TI MT puede tener política corporativa propia.

Posibles destinos de hosting:
- **AWS Middle East (UAE)** — region ME-Central-1 (Dubai), GA 2022. Postgres RDS + S3 + EC2.
- **AWS Bahrain** — region ME-South-1, alternativa.
- **AWS Frankfurt (eu-central-1)** — bajo latencia razonable a UAE (~80 ms), gran ecosistema.
- **Azure UAE** — North/Central regions disponibles.
- **GCP** — sin region UAE; más cercano Tel Aviv o Frankfurt.
- **Cloudflare** — distribución edge global; R2 en US/EU.

## Decisión

**OPEN — pendiente firma TI MT en S0**.

Recomendación BR (sujeta a aceptación):

### Default Fase 1 (si TI MT no exige residency UAE)

- **Compute (Next.js + Workers)**: Vercel / Railway / Fly.io regiones EU-Frankfurt o UAE si disponibles.
- **Postgres**: AWS RDS Frankfurt **o** Supabase managed EU **o** Azure Postgres UAE.
- **Redis**: Upstash EU.
- **Object storage**: Cloudflare R2 (edge global, sin residencia UAE pero replicado).
- **Logs/Metrics**: Better Stack EU.
- **Backups**: cross-region (UAE + Frankfurt si disponible).

### Si TI MT exige residencia UAE estricta

- **Compute**: AWS UAE region o Azure UAE.
- **Postgres**: AWS RDS UAE o Azure Postgres UAE.
- **Object storage**: AWS S3 UAE.
- **Logs**: vendor con region UAE o self-hosted Grafana Stack.
- Coste: probablemente +20-50 % vs EU (tariffing + ecosistema más limitado).
- Trade-off: mayor latencia desde devs BR (España) durante desarrollo.

### Si MT permite EU + replica UAE

- Compromiso: hot prod en EU; backup snapshot diario a S3 UAE.
- Requiere acuerdo contractual de uso.

### Backup + DR

- **RPO objetivo**: 1 hora (point-in-time recovery + WAL shipping).
- **RTO objetivo**: 4 horas (restore en region alternativa + redirección DNS).
- Backups encriptados, retenidos 30 días hot + 5 años cold (compliance VAT UAE).
- Test de restore trimestral.

## Alternativas evaluadas

### Alternativa A: AWS UAE region default
- **Pros**: máxima cobertura compliance.
- **Contras**: ecosistema más limitado, coste, BR devs UAT con latencia.
- **Veredicto**: si TI MT exige.

### Alternativa B: Cloudflare-only stack
- **Pros**: edge, simple.
- **Contras**: Cloudflare D1 / Hyperdrive aún no madurez para Postgres production con triggers + extensions.
- **Veredicto**: descartada.

### Alternativa C: Self-hosted en datacenter UAE
- **Pros**: control total.
- **Contras**: ops cost altísimo; incompatible con equipo pequeño BR.
- **Veredicto**: descartada salvo que MT tenga infra previa.

## Consecuencias positivas

- Decisión deferida a S0 con datos reales.
- Recomendación BR pragmática.
- Plan B documentado.

## Consecuencias negativas / riesgos

- Si TI MT decide tarde (post S0), bloquea inicio de S1. Mitigación: gating S0 explícito.
- Cambiar región post-go-live es caro y tedioso. Mitigación: decidir bien la primera vez.
- Multi-region complica DR. Mitigación: empezar single region UAE o EU; multi-region Fase 2+.

## Cuándo revisar

- **S0**: decisión obligatoria.
- **Pre-Fase 3** (storefront B2C): re-evaluar con tráfico real desde usuarios UAE finales.
- **Cualquier nueva regulación UAE**: re-evaluar.
