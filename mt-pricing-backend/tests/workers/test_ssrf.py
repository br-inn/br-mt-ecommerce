"""Tests SSRF guard — batería de >18 vectores cubriendo ADR-055.

Ref:
- ADR-055 §5 (test vectors enumerados).
- US-1A-02-07.

Cada test mockea `socket.getaddrinfo` cuando hace falta para evitar DNS real
en CI. Para tests de fetch con redirects usamos `respx` (declarado en
dependency-groups.dev del pyproject).
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import patch

import pytest

from app.services import ssrf as ssrf_module
from app.services.ssrf import (
    ALLOWED_CONTENT_TYPES,
    SSRFViolation,
    safe_fetch_image,
    validate_url,
)


# =============================================================================
# Helpers
# =============================================================================
def _mock_dns(ip_str: str | list[str]):
    """Mockea `socket.getaddrinfo` para devolver IPs deterministas."""
    ips = [ip_str] if isinstance(ip_str, str) else ip_str

    def fake(host, port, *args: Any, **kwargs: Any):
        out = []
        for ip in ips:
            family = socket.AF_INET6 if ":" in ip else socket.AF_INET
            out.append((family, socket.SOCK_STREAM, 0, "", (ip, port)))
        return out

    return patch.object(socket, "getaddrinfo", side_effect=fake)


# =============================================================================
# Vector #1-2: scheme blocking
# =============================================================================
class TestSchemeAllowlist:
    def test_http_blocked_in_default_env(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("http://example.com/foo.jpg")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("file:///etc/passwd")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_ftp_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("ftp://example.com/file")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_gopher_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("gopher://example.com:70/_GET /")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_data_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("data:image/png;base64,AAAA")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_javascript_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("javascript:alert(1)")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_dict_scheme_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("dict://localhost:11211/stats")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_empty_url_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("")
        assert exc.value.code == "ssrf_blocked_scheme"

    def test_oversized_url_blocked(self):
        long_url = "https://example.com/" + "a" * 3000
        with pytest.raises(SSRFViolation):
            validate_url(long_url)


# =============================================================================
# Vector #3-8: IP denylist (IPv4 + IPv6)
# =============================================================================
class TestIPDenylist:
    def test_localhost_literal_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://127.0.0.1/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_localhost_resolves_blocked(self):
        with _mock_dns("127.0.0.1"):
            with pytest.raises(SSRFViolation) as exc:
                validate_url("https://localhost/foo")
            assert exc.value.code == "ssrf_blocked_ip"

    def test_aws_imds_blocked(self):
        # 169.254.169.254 — IMDS metadata.
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://169.254.169.254/latest/meta-data/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_rfc1918_10_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://10.0.0.1/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_rfc1918_172_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://172.16.5.10/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_rfc1918_192_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://192.168.1.1/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_carrier_grade_nat_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://100.64.0.1/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://[::1]/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_ipv6_link_local_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://[fe80::1]/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_ipv6_ula_blocked(self):
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://[fc00::1]/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_ipv4_mapped_v6_blocked(self):
        # IPv4 127.0.0.1 mapped en IPv6.
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://[::ffff:127.0.0.1]/")
        assert exc.value.code == "ssrf_blocked_ip"

    def test_multi_a_record_one_private_blocked(self):
        # Vector #18: DNS multi-A donde una pública y otra 10.0.0.1.
        with _mock_dns(["8.8.8.8", "10.0.0.1"]):
            with pytest.raises(SSRFViolation) as exc:
                validate_url("https://example.com/img.jpg")
            assert exc.value.code == "ssrf_blocked_ip"

    def test_multi_a_record_all_public_ok(self):
        with _mock_dns(["8.8.8.8", "1.1.1.1"]):
            target = validate_url("https://example.com/img.jpg")
            assert target.host == "example.com"
            assert len(target.resolved_ips) == 2

    def test_dns_failure_blocked(self):
        def fake_fail(*args: Any, **kwargs: Any):
            raise socket.gaierror("name not found")

        with patch.object(socket, "getaddrinfo", side_effect=fake_fail):
            with pytest.raises(SSRFViolation) as exc:
                validate_url("https://does-not-exist.invalid/")
            assert exc.value.code == "ssrf_blocked_dns"


# =============================================================================
# Vector #16-17: PIM España feature flag (R-044)
# =============================================================================
class TestPimEsFeatureFlag:
    def test_pim_es_blocked_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(ssrf_module.settings, "ALLOW_PROBE_FROM_PIM_ES", False, raising=False)
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://pim.mt-valves.es/img/MT-V-038.jpg")
        assert exc.value.code == "image_rights_pending"

    def test_pim_es_subdomain_also_blocked(self, monkeypatch):
        monkeypatch.setattr(ssrf_module.settings, "ALLOW_PROBE_FROM_PIM_ES", False, raising=False)
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://media.mt-valves.es/img.jpg")
        assert exc.value.code == "image_rights_pending"

    def test_pim_es_allowed_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(ssrf_module.settings, "ALLOW_PROBE_FROM_PIM_ES", True, raising=False)
        with _mock_dns("8.8.8.8"):
            target = validate_url("https://pim.mt-valves.es/img/MT-V-038.jpg")
            assert target.host == "pim.mt-valves.es"

    def test_non_pim_host_not_gated(self, monkeypatch):
        monkeypatch.setattr(ssrf_module.settings, "ALLOW_PROBE_FROM_PIM_ES", False, raising=False)
        with _mock_dns("8.8.8.8"):
            target = validate_url("https://manufacturer.example.com/cat.png")
            assert target.host == "manufacturer.example.com"


# =============================================================================
# Extra CIDRs (TI MT runtime config)
# =============================================================================
class TestExtraBlockedCidrs:
    def test_extra_cidr_blocks_ip(self, monkeypatch):
        monkeypatch.setattr(
            ssrf_module.settings, "SSRF_EXTRA_BLOCKED_CIDRS", ["8.8.8.0/24"], raising=False
        )
        with pytest.raises(SSRFViolation) as exc:
            validate_url("https://8.8.8.8/")
        assert exc.value.code == "ssrf_blocked_ip"


# =============================================================================
# Vector #12-15: safe_fetch_image (Content-Type, oversize, redirects)
# =============================================================================
class TestSafeFetchImage:
    """Tests con respx para mockear httpx."""

    @pytest.fixture(autouse=True)
    def _mock_dns_public(self, monkeypatch):
        # Cualquier DNS resuelve a IP pública en estos tests.
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda host, port, *a, **kw: [
                (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port))
            ],
        )

    def test_svg_content_type_rejected(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://example.com/file.svg").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/svg+xml"},
                    content=b"<svg></svg>",
                )
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/file.svg")
            assert exc.value.code == "ssrf_blocked_mime"

    def test_oversize_content_length_rejected(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            big = 12 * 1024 * 1024
            mock.get("https://example.com/big.jpg").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/jpeg", "content-length": str(big)},
                    content=b"\xff\xd8\xff" + b"\x00" * 100,
                )
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/big.jpg", max_bytes=10 * 1024 * 1024)
            assert exc.value.code == "ssrf_blocked_oversize"

    def test_oversize_streaming_rejected(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            # Sin Content-Length declarado → cap durante stream.
            payload = b"\xff\xd8\xff" + b"\x00" * (200 * 1024)  # 200 KB+
            mock.get("https://example.com/medium.jpg").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/jpeg"},
                    content=payload,
                )
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/medium.jpg", max_bytes=100 * 1024)
            assert exc.value.code == "ssrf_blocked_oversize"

    def test_redirect_to_internal_blocked(self, monkeypatch):
        respx = pytest.importorskip("respx")
        import httpx

        # Redirect: example.com → 10.0.0.1. El 2do hop debe fallar SSRF.
        # Mockeamos DNS por host: example.com → public, evil.example → 10.0.0.1.
        def fake_dns(host, port, *a, **kw):
            ip = "93.184.216.34" if host == "example.com" else "10.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_dns)

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://example.com/").mock(
                return_value=httpx.Response(302, headers={"location": "https://evil.example/"})
            )
            mock.get("https://evil.example/").mock(
                return_value=httpx.Response(200, content=b"\xff\xd8\xff\x00")
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/")
            assert exc.value.code == "ssrf_blocked_ip"

    def test_too_many_redirects_blocked(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            # Cadena de 5 redirects a sí mismo.
            mock.get("https://example.com/loop").mock(
                return_value=httpx.Response(302, headers={"location": "https://example.com/loop"})
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/loop", max_redirects=2)
            assert exc.value.code == "ssrf_blocked_redirect"

    def test_magic_bytes_mismatch_rejected(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            # Server dice JPEG, contenido es HTML.
            mock.get("https://example.com/fake.jpg").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/jpeg"},
                    content=b"<html><body>haha</body></html>",
                )
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/fake.jpg")
            assert exc.value.code == "ssrf_blocked_mime"

    def test_valid_jpeg_ok(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 1024
            mock.get("https://example.com/img.jpg").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/jpeg"},
                    content=jpeg_bytes,
                )
            )
            result = safe_fetch_image("https://example.com/img.jpg")
            assert result.detected_mime == "image/jpeg"
            assert result.bytes_downloaded == len(jpeg_bytes)
            assert result.sha256  # 64-char hex
            assert len(result.sha256) == 64

    def test_valid_png_ok(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024
            mock.get("https://example.com/img.png").mock(
                return_value=httpx.Response(
                    200,
                    headers={"content-type": "image/png"},
                    content=png_bytes,
                )
            )
            result = safe_fetch_image("https://example.com/img.png")
            assert result.detected_mime == "image/png"

    def test_404_treated_as_violation(self):
        respx = pytest.importorskip("respx")
        import httpx

        with respx.mock(assert_all_called=False) as mock:
            mock.get("https://example.com/missing.jpg").mock(
                return_value=httpx.Response(404)
            )
            with pytest.raises(SSRFViolation) as exc:
                safe_fetch_image("https://example.com/missing.jpg")
            assert exc.value.code == "ssrf_blocked_http"


# =============================================================================
# Allowlist sanity checks
# =============================================================================
def test_allowed_content_types_set():
    assert "image/jpeg" in ALLOWED_CONTENT_TYPES
    assert "image/png" in ALLOWED_CONTENT_TYPES
    assert "image/webp" in ALLOWED_CONTENT_TYPES
    assert "image/gif" in ALLOWED_CONTENT_TYPES
    assert "image/svg+xml" not in ALLOWED_CONTENT_TYPES
