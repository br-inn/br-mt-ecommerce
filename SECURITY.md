# Política de seguridad

## Reportar una vulnerabilidad

La seguridad de MT Middle East y de los datos que esta plataforma procesa es
una prioridad absoluta para BR Innovation. Si descubrís una vulnerabilidad,
**te pedimos que NO abras un GitHub Issue público**.

### Canal preferido

- **Email**: `security@br-innovation.com` *(placeholder — confirmar dirección
  definitiva con BR/MT antes de go-live)*.
- **PGP**: clave pública disponible bajo pedido al mismo email.
- **Asunto sugerido**: `[SECURITY][br-mt-ecommerce] <breve descripción>`.

Incluí en tu reporte:

1. Descripción del problema.
2. Pasos exactos para reproducirlo (PoC si es posible).
3. Versión / commit / entorno donde lo encontraste.
4. Impacto potencial (lectura no autorizada, RCE, escalación de privilegios,
   bypass de RLS, etc.).
5. Mitigaciones temporales sugeridas, si las hay.
6. Tu información de contacto y si querés ser acreditado en un eventual
   acknowledgment.

### Tiempos de respuesta esperados

| Severidad | Acknowledge inicial | Triage completo | Patch / mitigación |
|---|---|---|---|
| Critical (RCE, exfil masiva) | < 24 h | < 48 h | < 7 días |
| High (auth bypass, RLS bypass) | < 24 h | < 72 h | < 14 días |
| Medium | < 72 h | < 7 días | < 30 días |
| Low / informational | < 7 días | < 14 días | siguiente release |

Si no recibís respuesta en 72 h al canal anterior, escribinos a
`psierra@br-innovation.com` como escalación.

## Disclosure responsable

Pedimos un período de **disclosure coordinado de 90 días** (o hasta que esté
disponible un patch oficial, lo que ocurra primero). Si necesitás extensiones
o tu hallazgo está siendo explotado activamente, contactanos para
sincronizar.

## Scope

Cubierto por esta política:

- Código y configuraciones en este monorepo (`mt-pricing-backend`,
  `mt-pricing-frontend`, `infra/`, `supabase/`, `_bmad-output/`).
- Endpoints expuestos del despliegue oficial (frontend, API, observabilidad).
- Imágenes Docker construidas a partir de este repo.
- Pipelines CI/CD configurados en este repositorio.
- Secrets management (Doppler) en lo referente a integración con este sistema.

**Fuera de scope**:

- Vulnerabilidades en versiones legacy o forks no oficiales.
- Vulnerabilidades en infraestructura de terceros gestionada externamente
  (Hetzner, Supabase, Cloudflare, etc.) — reportar directamente al proveedor;
  podés CC a este canal para coordinación.
- Issues que requieran acceso físico al servidor o que asuman compromiso
  total previo de credenciales.
- Reportes automatizados de scanners sin PoC ni impacto demostrado.
- Best-practices generales no asociadas a una vulnerabilidad concreta
  (preferimos discutirlas como ADR o issue normal).

## Acknowledgments

Mantenemos un *Hall of Fame* informal de quienes nos ayudan a mejorar la
seguridad del producto. Tras la resolución de un reporte, te ofrecemos:

- Crédito público (si lo deseás) en el `CHANGELOG.md` y en una sección de
  agradecimientos en este archivo.
- Comunicación coordinada del fix.
- En reportes de impacto significativo, evaluación caso a caso de
  reconocimiento adicional con MT/BR.

Gracias por ayudarnos a mantener segura la plataforma.
