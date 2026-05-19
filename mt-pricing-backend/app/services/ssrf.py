"""SSRF guard — política centralizada para probe + mirror de imágenes externas.

Ref:
- ADR-055 "Política SSRF para probe + mirror de imágenes externas".
- Risk register R-022 (SSRF importer URL probe).
- Risk register R-044 + Q-09 (image rights MT España, feature flag PIM).
- Sprint 2 backlog US-1A-02-07.

Diseño:
- Validador puro síncrono (`validate_url`) para uso desde routes (rechazo HTTP
  inmediato) y desde el worker Celery (rechazo antes de descargar).
- Función de fetch (`safe_fetch_image`) que aplica validación + redirect loop
  manual + Content-Length pre-check + streaming con cap.
- Excepción dedicada `SSRFViolation` con `code` discreto para mapping HTTP.

Importable desde routes:

    from app.services.ssrf import validate_url, SSRFViolation
    try:
        validate_url(url)
    except SSRFViolation as e:
        raise HTTPException(422, detail={"code": e.code, "message": str(e)})
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from typing import Final
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Constants — denylist canónica + content-type allowlist
# =============================================================================

# Default denylist — se complementa con `settings.SSRF_EXTRA_BLOCKED_CIDRS`.
# Servidor en AWS EC2: el IMDS endpoint 169.254.169.254 ya está bloqueado por el rango 169.254.0.0/16.
_DEFAULT_BLOCKED_CIDRS_V4: Final[tuple[str, ...]] = (
    "0.0.0.0/8",          # current network (RFC 1700)
    "10.0.0.0/8",         # RFC 1918 private
    "100.64.0.0/10",      # RFC 6598 carrier-grade NAT
    "127.0.0.0/8",        # loopback
    "169.254.0.0/16",     # link-local (incl. AWS/GCP IMDS 169.254.169.254)
    "172.16.0.0/12",      # RFC 1918 private
    "192.0.0.0/24",       # IETF protocol assignments
    "192.0.2.0/24",       # TEST-NET-1
    "192.168.0.0/16",     # RFC 1918 private
    "198.18.0.0/15",      # benchmarking (RFC 2544)
    "198.51.100.0/24",    # TEST-NET-2
    "203.0.113.0/24",     # TEST-NET-3
    "224.0.0.0/4",        # multicast
    "240.0.0.0/4",        # reserved (incl. broadcast 255.255.255.255)
)
_DEFAULT_BLOCKED_CIDRS_V6: Final[tuple[str, ...]] = (
    "::/128",             # unspecified
    "::1/128",            # loopback
    "::ffff:0:0/96",      # IPv4-mapped — re-checked after extracting v4
    "64:ff9b::/96",       # NAT64 well-known
    "fc00::/7",           # ULA private
    "fe80::/10",          # link-local
    "ff00::/8",           # multicast
)

ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"https"})
ALLOWED_SCHEMES_DEV: Final[frozenset[str]] = frozenset({"http", "https"})

ALLOWED_CONTENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)

# Magic bytes para verificación post-fetch (no confiar en Content-Type del
# server). Coincide con `image_service.py` pero más estricto: no aceptamos
# AVIF aquí (S2 scope).
_MAGIC_PREFIXES: Final[dict[str, tuple[bytes, ...]]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    # WebP: RIFF + WEBP — chequeado especial en `_detect_mime`.
    "image/webp": (b"RIFF",),
}

# Hosts canónicos del PIM MT España — gated por `ALLOW_PROBE_FROM_PIM_ES`.
# TODO sponsor MT: confirmar lista exhaustiva. Default conservador.
_DEFAULT_PIM_ES_HOSTS: Final[tuple[str, ...]] = (
    "pim.mt-valves.es",
    "static.mt-valves.es",
    "media.mt-valves.es",
)


# =============================================================================
# Exceptions
# =============================================================================
class SSRFViolation(Exception):
    """Una URL no pasó el guard SSRF. `code` es estable para mapping HTTP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# =============================================================================
# Result type — parsing previo
# =============================================================================
@dataclass(frozen=True)
class _ParsedTarget:
    scheme: str
    host: str
    port: int
    resolved_ips: tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...] = field(
        default_factory=tuple
    )


# =============================================================================
# Helpers
# =============================================================================
def _allowed_schemes() -> frozenset[str]:
    """Devuelve schemes permitidos según ENV + flag override."""
    if settings.ENV == "development" and getattr(settings, "ALLOW_HTTP_PROBE", False):
        return ALLOWED_SCHEMES_DEV
    return ALLOWED_SCHEMES


def _build_blocked_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Combina denylist canónica + extras configurados en settings."""
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in _DEFAULT_BLOCKED_CIDRS_V4 + _DEFAULT_BLOCKED_CIDRS_V6:
        nets.append(ipaddress.ip_network(cidr, strict=False))
    extras = getattr(settings, "SSRF_EXTRA_BLOCKED_CIDRS", None) or ()
    for cidr in extras:
        try:
            nets.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            logger.warning("ssrf.invalid_extra_cidr", extra={"cidr": cidr})
    return tuple(nets)


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Comprueba la IP contra la denylist + flags `is_*` de stdlib."""
    # Defensa-en-profundidad: chequeo flags estándar de la stdlib.
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True
    # IPv4-mapped IPv6 → extraer y revalidar como v4.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return _ip_is_blocked(ip.ipv4_mapped)
    for net in _build_blocked_networks():
        if ip in net:
            return True
    return False


def _resolve_host(
    host: str, port: int
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    """Resolución DNS A+AAAA. Devuelve tupla de IPs o lanza SSRFViolation."""
    # Si el host ya es una IP literal, parse directo (no llamar a DNS).
    try:
        ip = ipaddress.ip_address(host)
        return (ip,)
    except ValueError:
        pass

    try:
        # AF_UNSPEC → A + AAAA.
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SSRFViolation("ssrf_blocked_dns", f"DNS resolution failed: {e}") from e

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        try:
            ips.append(ipaddress.ip_address(ip_str))
        except ValueError:
            continue
    if not ips:
        raise SSRFViolation("ssrf_blocked_dns", f"No A/AAAA records for {host}")
    # Dedupe preservando orden.
    seen: set[str] = set()
    uniq: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for ip in ips:
        key = str(ip)
        if key not in seen:
            seen.add(key)
            uniq.append(ip)
    return tuple(uniq)


def _is_pim_es_host(host: str) -> bool:
    allowlist = getattr(settings, "PIM_ES_HOST_ALLOWLIST", None) or _DEFAULT_PIM_ES_HOSTS
    host_l = host.lower()
    return any(host_l == h.lower() or host_l.endswith("." + h.lower()) for h in allowlist)


def _detect_mime(prefix_bytes: bytes) -> str | None:
    """Detección por magic bytes — devuelve MIME o None."""
    if (
        len(prefix_bytes) >= 12
        and prefix_bytes[:4] == b"RIFF"
        and prefix_bytes[8:12] == b"WEBP"
    ):
        return "image/webp"
    for mime, prefixes in _MAGIC_PREFIXES.items():
        if mime == "image/webp":
            continue
        for p in prefixes:
            if prefix_bytes.startswith(p):
                return mime
    return None


# =============================================================================
# Public API — synchronous validator
# =============================================================================
def validate_url(url: str) -> _ParsedTarget:
    """Valida una URL contra la política SSRF.

    Pasos:
    1. Parse + scheme allowlist.
    2. Hostname requerido.
    3. PIM España gating si aplica (`ALLOW_PROBE_FROM_PIM_ES`).
    4. Resolución DNS A+AAAA.
    5. Cada IP resuelta validada contra denylist.

    Retorna `_ParsedTarget` con metadata (host, IPs resueltas) — útil para
    el caller que quiera loggear o reusar.

    Lanza `SSRFViolation` con `code` discreto en cualquier fallo.
    """
    if not url or not isinstance(url, str):
        raise SSRFViolation("ssrf_blocked_scheme", "URL vacía o no string")
    if len(url) > 2048:
        raise SSRFViolation("ssrf_blocked_scheme", "URL excede 2048 chars")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _allowed_schemes():
        raise SSRFViolation(
            "ssrf_blocked_scheme",
            f"esquema {scheme!r} no permitido (sólo {sorted(_allowed_schemes())})",
        )

    host = (parsed.hostname or "").strip()
    if not host:
        raise SSRFViolation("ssrf_blocked_scheme", "URL sin hostname")

    # Puerto: si scheme es https default 443, http default 80.
    port = parsed.port or (443 if scheme == "https" else 80)

    # PIM ES gating (R-044 / Q-09) — antes de DNS para no leakear queries.
    if _is_pim_es_host(host) and not getattr(settings, "ALLOW_PROBE_FROM_PIM_ES", False):
        raise SSRFViolation(
            "image_rights_pending",
            f"host PIM España {host!r} requiere acuerdo legal Q-09 (ALLOW_PROBE_FROM_PIM_ES=False)",
        )

    ips = _resolve_host(host, port)
    for ip in ips:
        if _ip_is_blocked(ip):
            raise SSRFViolation(
                "ssrf_blocked_ip",
                f"host {host!r} resuelve a IP bloqueada {ip}",
            )

    return _ParsedTarget(scheme=scheme, host=host, port=port, resolved_ips=ips)


# =============================================================================
# Public API — safe fetch (con redirect loop manual + cap streaming)
# =============================================================================
@dataclass(frozen=True)
class FetchResult:
    """Resultado de `safe_fetch_image` — bytes + metadata."""

    content: bytes
    detected_mime: str
    final_url: str
    sha256: str
    bytes_downloaded: int


def safe_fetch_image(
    url: str,
    *,
    max_bytes: int | None = None,
    max_redirects: int | None = None,
    timeout_s: float | None = None,
    client: httpx.Client | None = None,
) -> FetchResult:
    """Descarga una imagen aplicando el guard SSRF en cada hop de redirect.

    Args:
        url: URL inicial a probe.
        max_bytes: cap de tamaño en bytes (default `settings.SSRF_MAX_BYTES`,
            10 MB).
        max_redirects: hops máximos (default `settings.SSRF_MAX_REDIRECTS`, 3).
        timeout_s: total timeout (default 30s).
        client: opcional `httpx.Client` (para tests con `respx`).

    Lanza `SSRFViolation` en cualquier fallo de política.
    """
    import hashlib

    max_bytes = max_bytes if max_bytes is not None else getattr(settings, "SSRF_MAX_BYTES", 10 * 1024 * 1024)
    max_redirects = (
        max_redirects if max_redirects is not None else getattr(settings, "SSRF_MAX_REDIRECTS", 3)
    )
    timeout_s = timeout_s if timeout_s is not None else 30.0

    own_client = client is None
    if own_client:
        client = httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_s, connect=5.0),
            headers={"User-Agent": "mt-image-probe/1.0"},
        )

    try:
        current_url = url
        for hop in range(max_redirects + 1):
            target = validate_url(current_url)  # raises SSRFViolation
            try:
                with client.stream("GET", current_url) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise SSRFViolation(
                                "ssrf_blocked_redirect",
                                f"redirect {response.status_code} sin Location",
                            )
                        # Resolver location relativo respecto a current_url.
                        if location.startswith("/"):
                            location = f"{target.scheme}://{target.host}{location}"
                        current_url = location
                        continue

                    if response.status_code >= 400:
                        raise SSRFViolation(
                            "ssrf_blocked_http",
                            f"HTTP {response.status_code} desde {current_url}",
                        )

                    # Content-Length pre-check.
                    cl = response.headers.get("content-length")
                    if cl is not None:
                        try:
                            cl_int = int(cl)
                            if cl_int > max_bytes:
                                raise SSRFViolation(
                                    "ssrf_blocked_oversize",
                                    f"Content-Length {cl_int} > {max_bytes}",
                                )
                        except ValueError:
                            pass  # ignoramos Content-Length malformado, validamos con stream cap

                    # Content-Type allowlist (servidor declarado).
                    raw_ct = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if raw_ct and raw_ct not in ALLOWED_CONTENT_TYPES:
                        raise SSRFViolation(
                            "ssrf_blocked_mime",
                            f"Content-Type {raw_ct!r} no permitido",
                        )

                    # Streaming con cap.
                    chunks: list[bytes] = []
                    total = 0
                    hasher = hashlib.sha256()
                    for chunk in response.iter_bytes(chunk_size=64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise SSRFViolation(
                                "ssrf_blocked_oversize",
                                f"stream excede {max_bytes} bytes",
                            )
                        chunks.append(chunk)
                        hasher.update(chunk)

                    body = b"".join(chunks)
                    detected = _detect_mime(body[:32])
                    if detected is None:
                        raise SSRFViolation(
                            "ssrf_blocked_mime",
                            "magic bytes no reconocidos (¿html, svg, exe?)",
                        )
                    if detected not in ALLOWED_CONTENT_TYPES:
                        raise SSRFViolation(
                            "ssrf_blocked_mime",
                            f"MIME detectado {detected!r} no permitido",
                        )
                    # Cross-check: si Content-Type estaba presente, debe coincidir
                    # con magic bytes (defensa contra spoof).
                    if raw_ct and raw_ct != detected:
                        raise SSRFViolation(
                            "ssrf_blocked_mime",
                            f"Content-Type declarado {raw_ct!r} != detectado {detected!r}",
                        )

                    return FetchResult(
                        content=body,
                        detected_mime=detected,
                        final_url=current_url,
                        sha256=hasher.hexdigest(),
                        bytes_downloaded=total,
                    )
            except httpx.TimeoutException as e:
                raise SSRFViolation("ssrf_blocked_timeout", f"timeout: {e}") from e
            except httpx.RequestError as e:
                raise SSRFViolation("ssrf_blocked_network", f"network error: {e}") from e

        raise SSRFViolation("ssrf_blocked_redirect", f"superados {max_redirects} redirects")
    finally:
        if own_client and client is not None:
            client.close()
