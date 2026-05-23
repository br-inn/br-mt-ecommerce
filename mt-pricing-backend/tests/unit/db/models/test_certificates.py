"""Unit tests for Certificate ORM — pure Python (no DB)."""

import uuid
from datetime import date
from app.db.models.certificates import Certificate, CertificateScope


def test_certificate_instantiation():
    cert = Certificate(
        id=uuid.uuid4(),
        cert_number="23 ACC LY 482",
        certification_id=uuid.uuid4(),
        model_id=uuid.uuid4(),
        issuer="Carso",
        issued_at=date(2023, 7, 11),
        expires_at=date(2028, 7, 11),
        status="valid",
    )
    assert cert.cert_number == "23 ACC LY 482"
    assert cert.status == "valid"


def test_certificate_scope_instantiation():
    scope = CertificateScope(
        certificate_id=uuid.uuid4(),
        sku="4097015",
    )
    assert scope.sku == "4097015"
    assert scope.dn_min is None
