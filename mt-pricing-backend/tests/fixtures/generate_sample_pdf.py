"""Script para generar tests/fixtures/sample_equivalences.pdf.

Ejecutar una vez:
    python tests/fixtures/generate_sample_pdf.py

También invocado automáticamente por conftest.py si el PDF no existe.
"""

from __future__ import annotations

import pathlib


def build_pdf() -> bytes:
    """Construye un PDF mínimo válido con texto de equivalencias."""
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>\nendobj\n"
    )
    obj4 = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    stream_body = (
        b"BT /F1 12 Tf 50 750 Td "
        b"(MT-VALVE-001 = MT-VALVE-002) Tj "
        b"0 -20 Td (MT-PUMP-100 equiv. MT-PUMP-101) Tj ET"
    )
    obj5 = (
        b"5 0 obj\n<< /Length "
        + str(len(stream_body)).encode()
        + b" >>\nstream\n"
        + stream_body
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    offsets: list[int] = []
    body = header
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(len(body))
        body += obj

    xref_offset = len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += (str(off).zfill(10) + " 00000 n \n").encode()

    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    return body + xref + trailer


def main() -> None:
    dest = pathlib.Path(__file__).parent / "sample_equivalences.pdf"
    dest.write_bytes(build_pdf())
    print(f"Generated {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
