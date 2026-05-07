# ADR-055 — Política SSRF para probe + mirror de imágenes externas

> Renumbrada respecto al brief Sprint 2 (que pedía "ADR-047") porque ADR-047
> ya existe y trata el observability stack. Se asigna el siguiente número libre.

- **Estado**: Proposed (firma pendiente — sponsor seguridad MT + TI MT)
- **Fecha**: 2026-05-07
- **Sprint**: S2 (US-1A-02-07)
- **Riesgos asociados**: R-022 (SSRF importer), R-044 (image rights MT España), Q-09
- **Autores**: Equipo backend BR (Agente 3 Sprint 2)
- **Reemplaza**: N/A
- **Reemplazada por**: N/A

---

## 1. Contexto

La épica EP-1A-02 (gestión imágenes) requiere descargar imágenes desde URLs
externas (`pim.mt-valves.es`, sitios de fabricantes) y mirrorearlas al bucket
interno `product-images` de Supabase Storage. Ese campo `image_url_pim` viene
de un PIM controlado por terceros — un actor malicioso puede inyectar URLs
apuntando a:

- **Metadata IMDS de cloud** (`http://169.254.169.254/latest/meta-data/`) →
  fuga del token IAM/credenciales del nodo Hetzner. Catalogado en R-022 (score
  12, Critical).
- **Servicios internos** (`http://localhost:8000/health/ready`,
  `http://10.0.0.5:5432`) → reconocimiento de la red interna o ataque a
  servicios sin auth tras el firewall.
- **Loopback IPv6** (`http://[::1]/admin`) → mismo vector vía IPv6.
- **Esquemas no-HTTP** (`file:///etc/passwd`, `gopher://`, `ftp://`) →
  exfiltración de archivos del worker o pivote a otros servicios.
- **Redirects** que primero responden a un host público y luego saltan a IP
  interna (`https://attacker.com/r → http://10.0.0.1`) — DNS rebinding o
  redirect chains.

Sin defensa explícita, el worker Celery con permisos service-role se convierte
en confused deputy con acceso a la red interna del proyecto. La penetration
test interna BR-2024-Q4 ya identificó este patrón en otro stack.

Adicionalmente (R-044, Q-09): MT España todavía no firma el acuerdo legal que
autorice el mirror de imágenes desde su PIM. Mientras Q-09 esté abierta, el
mirror desde `pim.mt-valves.es` debe estar tras un feature flag desactivado
por defecto.

## 2. Decisión

Implementamos un **SSRF guard** centralizado (`app/services/ssrf.py`) que toda
descarga externa DEBE atravesar antes de hacer la request HTTP. La política
cubre:

### 2.1 Esquema y métodos

- Solo `https://` aceptado en producción y staging.
- En `ENV=development` se permite `http://` si la flag `ALLOW_HTTP_PROBE=1`
  está activa (para fixtures locales). Nunca en `production` ni `staging`.
- Bloqueados explícitamente: `http://` (modo no-dev), `file://`, `ftp://`,
  `gopher://`, `data:`, `javascript:`, `dict://`, `ldap://`, cualquier otro
  esquema no listado.

### 2.2 Resolución DNS pre-fetch

- Para cada URL, resolver el hostname con `socket.getaddrinfo` (A + AAAA)
  ANTES de hacer la request.
- Validar **cada IP resuelta** contra la denylist canónica:
  - `0.0.0.0/8` (este host)
  - `10.0.0.0/8` (RFC 1918)
  - `127.0.0.0/8` (loopback)
  - `169.254.0.0/16` (link-local + IMDS AWS/GCP)
  - `172.16.0.0/12` (RFC 1918)
  - `192.0.0.0/24`, `192.0.2.0/24`, `198.18.0.0/15`, `198.51.100.0/24`,
    `203.0.113.0/24`, `224.0.0.0/4`, `240.0.0.0/4` (reservados/multicast/test)
  - `192.168.0.0/16` (RFC 1918)
  - `::1/128` (loopback IPv6)
  - `::/128` (unspecified)
  - `fc00::/7` (ULA IPv6)
  - `fe80::/10` (link-local IPv6)
  - `ff00::/8` (multicast IPv6)
  - `64:ff9b::/96` (NAT64 — opcional, conservador)
- **TODO infra**: la lista de rangos internos privados de Hetzner (vSwitch
  privado MT) debe ser confirmada por TI MT y añadida a la denylist via
  setting `SSRF_EXTRA_BLOCKED_CIDRS`. Hasta entonces se asume que Hetzner
  vSwitch usa `10.0.0.0/8` (cubierto por RFC 1918).
- Si **alguna** de las IPs resueltas cae en la denylist → `SSRFViolation`.
  No se acepta "alguna pública alguna privada" (defensa frente a DNS
  rebinding pasivo + multi-A).

### 2.3 Redirects

- Permitidos hasta 3 hops. Cada hop pasa la misma validación SSRF (esquema +
  DNS + IP) ANTES de seguirlo.
- `httpx` configurado con `follow_redirects=False`; el guard implementa el
  loop de redirects manualmente para poder validar.
- 4o+ hop → rechazo `redirect_loop`.

### 2.4 Timeouts y tamaño

- `connect`: 5s
- `read`: 30s
- `total`: 30s
- `Content-Length` declarado > 10 MB → rechazo `too_large` antes de stream.
- Streaming en chunks de 64 KB; si bytes acumulados > 10 MB → abort + delete.

### 2.5 Content-Type allowlist

Aceptados (debe matchear `Content-Type` cabecera Y magic bytes detectados):

- `image/jpeg` (mágico `FF D8 FF`)
- `image/png` (mágico `89 50 4E 47 0D 0A 1A 0A`)
- `image/webp` (mágico `RIFF....WEBP`)
- `image/gif` (mágico `GIF87a` / `GIF89a`)

**Rechazado explícitamente**: `image/svg+xml` — los SVG admiten `<script>`,
JavaScript inline, XLink a recursos externos. Mirar SVG no es trivial; lo
prohibimos de raíz.

### 2.6 Feature flag por origen

Setting nuevo `ALLOW_PROBE_FROM_PIM_ES: bool = False` (default `False`).
Mientras Q-09 (R-044) no esté firmada:

- Si la URL pertenece a `*.mt-valves.es` (lista en `PIM_ES_HOST_ALLOWLIST`),
  el guard rechaza con `code=image_rights_pending` aunque el resto sea OK.
- El audit log registra cada intento con `actor`, `sku`, `host` para evidencia
  legal posterior.

Sponsor MT decide cuándo flipar el flag a `True`. Toggle vía Doppler / env
sin redeploy.

### 2.7 Observabilidad y errores

Todos los rechazos producen:

- Log estructurado WARNING con campos `actor`, `sku`, `url_host`, `reason`,
  `resolved_ips`.
- Métrica Prometheus `images_ssrf_blocks_total{reason}` incrementada.
- Sentry breadcrumb (no error nivel) — pueden ser ataques activos pero el
  guard funcionando es comportamiento esperado.

Códigos de error retornados al cliente HTTP del endpoint probe:

| `error.code`              | Causa                                           |
| ------------------------- | ----------------------------------------------- |
| `ssrf_blocked_scheme`     | Esquema no permitido                            |
| `ssrf_blocked_ip`         | IP resuelta en denylist                         |
| `ssrf_blocked_dns`        | Resolución DNS falló o sin A/AAAA               |
| `ssrf_blocked_redirect`   | Redirect a host bloqueado                       |
| `ssrf_blocked_oversize`   | Content-Length > 10 MB                          |
| `ssrf_blocked_mime`       | Content-Type no permitido (incluye SVG)         |
| `image_rights_pending`    | Host bajo `ALLOW_PROBE_FROM_PIM_ES=False`       |

## 3. Alternativas consideradas

### 3.1 Proxy externo (Smokescreen, Stripe smokescreen-like)

**Rechazada**. Añade un service más al stack (otro container, otra red,
otra fuente de fallos), y depende de mantener la denylist en otro repo.
Para un proyecto single-tenant Fase 1 con < 10k probes/día es overkill.
Reconsiderar en Fase 1.5+ si el volumen crece.

### 3.2 Allowlist en lugar de denylist

**Rechazada parcialmente**. Una allowlist de hosts conocidos (PIM MT
España, sitios de fabricantes habituales) sería más segura, pero la lista
es desconocida ex-ante (el PIM puede contener URLs de cientos de
fabricantes). Se aplica allowlist secundaria: `ALLOW_PROBE_FROM_PIM_ES`
para R-044, denylist para R-022. En Fase 1.5 evaluar denylist + allowlist
combinada con UI admin.

### 3.3 Confiar en firewall egress de Hetzner

**Rechazada** como mitigación única. El firewall debe configurarse igualmente
(defense-in-depth — capa red), pero no podemos depender de él porque:

- En desarrollo local no hay firewall.
- Tests deben pasar sin firewall.
- Un cambio de configuración del firewall no debe abrir agujero en la app.

El firewall egress de Hetzner se documenta en
`mt-security-compliance-design.md §egress-rules` como capa complementaria.

## 4. Consecuencias

### Positivas

- R-022 mitigado: SSRF a IMDS / red interna bloqueado en la app, independiente
  del firewall.
- R-044 mitigado: feature flag granular permite cumplir con legal mientras
  se firma Q-09.
- Test vectors documentados → regresiones detectables en CI.
- Defensa-en-profundidad: app + firewall + Sentry alerting.

### Negativas

- +5-15ms de latencia por probe (DNS pre-resolve).
- Complejidad añadida: redirect loop manual, IP validation IPv4+IPv6.
- Falsos positivos posibles: si MT ME usa un PIM detrás de IP estática
  detrás de Hetzner vSwitch (mismo `10.x.x.x`), el guard lo bloquea.
  Mitigación: setting `SSRF_INTERNAL_PIM_ALLOWED_HOSTS` con allowlist de
  hosts que SÍ pueden resolver a IP privada (ojo: alto riesgo, requiere
  firma sponsor seguridad).
- DNS rebinding activo (TTL=0, IP cambia entre resolve y request) NO está
  cubierto al 100%. Para cobertura total habría que usar el mismo socket
  validado tras `getaddrinfo` (binding manual). Documentado como limitación
  conocida; el riesgo se considera bajo en Fase 1 (no exponemos al usuario
  final, solo TI MT).

## 5. Test vectors (regression battery)

Cada uno DEBE estar cubierto por test unitario en
`tests/workers/test_ssrf.py`:

| #   | Input                                                       | Resultado esperado          |
| --- | ----------------------------------------------------------- | --------------------------- |
| 1   | `http://localhost/foo`                                      | `ssrf_blocked_scheme` (HTTP en prod) o `ssrf_blocked_ip` |
| 2   | `https://localhost/foo`                                     | `ssrf_blocked_ip` (127.0.0.1) |
| 3   | `https://127.0.0.1/foo`                                     | `ssrf_blocked_ip`           |
| 4   | `http://169.254.169.254/latest/meta-data/`                  | `ssrf_blocked_ip` (IMDS)    |
| 5   | `https://10.0.0.1/`                                         | `ssrf_blocked_ip`           |
| 6   | `https://192.168.1.1/`                                      | `ssrf_blocked_ip`           |
| 7   | `https://[::1]/`                                            | `ssrf_blocked_ip` (IPv6 loopback) |
| 8   | `https://[fe80::1]/`                                        | `ssrf_blocked_ip` (IPv6 link-local) |
| 9   | `file:///etc/passwd`                                        | `ssrf_blocked_scheme`       |
| 10  | `ftp://example.com/`                                        | `ssrf_blocked_scheme`       |
| 11  | `gopher://example.com:70/`                                  | `ssrf_blocked_scheme`       |
| 12  | `https://example.com/file.svg` (Content-Type SVG)           | `ssrf_blocked_mime`         |
| 13  | `https://example.com/big` (Content-Length 12 MB)            | `ssrf_blocked_oversize`     |
| 14  | URL pública que redirige a `http://10.0.0.1`                | `ssrf_blocked_redirect`     |
| 15  | URL pública con 4 redirects                                 | `ssrf_blocked_redirect` (loop) |
| 16  | `https://pim.mt-valves.es/img.jpg` con flag PIM=False       | `image_rights_pending`      |
| 17  | `https://pim.mt-valves.es/img.jpg` con flag PIM=True        | OK (sigue validación normal) |
| 18  | DNS multi-A donde una IP es pública y otra `10.0.0.1`       | `ssrf_blocked_ip`           |

## 6. Implementación

- `mt-pricing-backend/app/services/ssrf.py` — guard validator.
- `mt-pricing-backend/app/workers/probe_mirror.py` — Celery task que aplica
  el guard antes de descargar.
- `mt-pricing-backend/app/workers/thumbnails.py` — Celery task downstream
  (ya post-mirror, no aplica SSRF).
- Settings nuevos: `ALLOW_PROBE_FROM_PIM_ES`, `ALLOW_HTTP_PROBE`,
  `PIM_ES_HOST_ALLOWLIST`, `SSRF_EXTRA_BLOCKED_CIDRS`,
  `SSRF_MAX_REDIRECTS`, `SSRF_MAX_BYTES`.

## 7. Trazabilidad

- PRD §14.6.4 (image probe).
- Risk register: R-022, R-044.
- Q-09 (legal Q rights).
- Sprint 2 backlog US-1A-02-07.
- mt-security-compliance-design.md §SSRF (a actualizar).
- mt-jobs-module-design.md (probe + mirror task).
